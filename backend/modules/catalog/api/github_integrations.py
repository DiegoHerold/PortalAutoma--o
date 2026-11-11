from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from infrastructure.github.client import GithubApiError, GithubAppClient, GithubAppNotConfiguredError
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.authentication import JwtTokenIssuer
from modules.catalog.api.schemas import (
    AutomationImportPreview,
    GithubConnectResponse,
    GithubDiscoverRequest,
    GithubImportRequest,
    GithubIntegrationResponse,
    GithubRepositoryResponse,
)
from modules.catalog.infrastructure.import_packaging import AutomationImportPackagingError, CatalogImportPackagingService
from modules.catalog.infrastructure.orm.models import GithubIntegrationRecord

router = APIRouter()


@router.get("", response_model=list[GithubIntegrationResponse])
def list_integrations(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[GithubIntegrationResponse]:
    _ensure_admin_or_manager(db, user)
    records = db.scalars(select(GithubIntegrationRecord).order_by(GithubIntegrationRecord.account_login)).all()
    return [GithubIntegrationResponse.model_validate(record, from_attributes=True) for record in records]


@router.post("/connect", response_model=GithubConnectResponse)
def connect(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> GithubConnectResponse:
    _ensure_admin_or_manager(db, user)
    client = _client_or_400()
    state = JwtTokenIssuer().create_access_token(str(user.id))
    try:
        install_url = client.install_url()
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        client.close()
    return GithubConnectResponse(install_url=f"{install_url}?state={state}")


@router.get("/callback")
def callback(
    installation_id: int = Query(...),
    setup_action: str = Query(default="install"),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    frontend_target = f"{settings.frontend_url}/settings/integrations"
    try:
        client = _client_or_400()
    except HTTPException:
        return RedirectResponse(url=f"{frontend_target}?github=error&reason=not_configured")

    if setup_action == "request":
        client.close()
        return RedirectResponse(url=f"{frontend_target}?github=pending")

    try:
        installation = client.get_installation(installation_id)
    except GithubApiError as exc:
        client.close()
        return RedirectResponse(url=f"{frontend_target}?github=error&reason={exc.status_code}")
    finally:
        client.close()

    connected_by_user_id = None
    if state:
        try:
            connected_by_user_id = int(JwtTokenIssuer().decode_access_token(state)["sub"])
        except Exception:
            connected_by_user_id = None

    account = installation.get("account", {})
    existing = db.scalar(select(GithubIntegrationRecord).where(GithubIntegrationRecord.installation_id == installation_id))
    if existing:
        existing.account_login = account.get("login", existing.account_login)
        existing.suspended_at = None
        db.add(existing)
    else:
        db.add(
            GithubIntegrationRecord(
                installation_id=installation_id,
                account_login=account.get("login", "unknown"),
                account_type=account.get("type", "User"),
                connected_by_user_id=connected_by_user_id,
                connected_at=datetime.now(UTC),
            )
        )
    db.commit()
    return RedirectResponse(url=f"{frontend_target}?github=connected")


@router.delete("/{integration_id}", status_code=204, response_model=None)
def disconnect(integration_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> None:
    _ensure_admin_or_manager(db, user)
    integration = db.get(GithubIntegrationRecord, integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integracao nao encontrada.")
    db.delete(integration)
    db.commit()


@router.get("/{integration_id}/repositories", response_model=list[GithubRepositoryResponse])
def list_repositories(
    integration_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[GithubRepositoryResponse]:
    _ensure_admin_or_manager(db, user)
    installation_id = _resolve_installation_id(db, integration_id)
    client = _client_or_400()
    try:
        repos = client.list_repositories(installation_id)
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        client.close()
    return [GithubRepositoryResponse(**repo.__dict__) for repo in repos]


@router.get("/{integration_id}/repositories/{owner}/{repository}/branches", response_model=list[str])
def list_branches(
    integration_id: int,
    owner: str,
    repository: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[str]:
    _ensure_admin_or_manager(db, user)
    installation_id = _resolve_installation_id(db, integration_id)
    client = _client_or_400()
    try:
        return client.list_branches(installation_id, owner, repository)
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        client.close()


@router.post("/{integration_id}/repositories/{owner}/{repository}/discover", response_model=list[AutomationImportPreview])
def discover(
    integration_id: int,
    owner: str,
    repository: str,
    payload: GithubDiscoverRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AutomationImportPreview]:
    _ensure_admin_or_manager(db, user)
    try:
        previews = CatalogImportPackagingService(db).discover_github(integration_id, owner, repository, payload.branch)
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AutomationImportPackagingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return [AutomationImportPreview.model_validate(preview) for preview in previews]


@router.post("/{integration_id}/import", response_model=list[AutomationImportPreview])
def import_selected(
    integration_id: int,
    payload: GithubImportRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AutomationImportPreview]:
    _ensure_admin_or_manager(db, user)
    try:
        service = CatalogImportPackagingService(db)
        previews = [
            service.stage_github_import(integration_id, payload.owner, payload.repository, payload.branch, manifest_path, user)
            for manifest_path in payload.manifest_paths
        ]
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AutomationImportPackagingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return [AutomationImportPreview.model_validate(preview) for preview in previews]


def _client_or_400() -> GithubAppClient:
    try:
        return GithubAppClient()
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_installation_id(db: Session, integration_id: int) -> int:
    integration = db.get(GithubIntegrationRecord, integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integracao nao encontrada.")
    return integration.installation_id


def _ensure_admin_or_manager(db: Session, user: Any) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_admin_or_manager(user)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
