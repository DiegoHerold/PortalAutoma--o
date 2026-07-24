from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token
from app.dependencies import get_current_user
from app.integrations.github.client import GithubApiError, GithubAppClient, GithubAppNotConfiguredError
from app.models.github_integration import GithubIntegration
from app.models.user import User
from app.repositories.github_integration_repository import GithubIntegrationRepository
from app.schemas.automation_import import AutomationImportPreview
from app.schemas.github_integration import (
    GithubConnectResponse,
    GithubDiscoverRequest,
    GithubImportRequest,
    GithubIntegrationRead,
    GithubRepositoryRead,
)
from app.services.github_discovery_service import GithubDiscoveryService
from app.services.permission_service import PermissionService
from app.utils.datetime import utcnow

router = APIRouter()


def _client_or_400() -> GithubAppClient:
    try:
        return GithubAppClient()
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_installation_id(db: Session, integration_id: int) -> int:
    """
    `integration_id` (path param) is our local GithubIntegration.id (DB primary
    key). The GitHub API needs the actual `installation_id` GitHub assigned to
    this installation — a different number. Every call into GithubAppClient
    must use the resolved value, never the raw path param.
    """
    integration = GithubIntegrationRepository(db).get(integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    return integration.installation_id


@router.get("", response_model=list[GithubIntegrationRead])
def list_integrations(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[GithubIntegrationRead]:
    PermissionService(db).ensure_admin_or_manager(user)
    return GithubIntegrationRepository(db).list_all()


@router.post("/connect", response_model=GithubConnectResponse)
def connect(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> GithubConnectResponse:
    """
    Returns the GitHub App installation URL. The frontend should navigate the
    top-level window to it (like Vercel's "Add GitHub Account" flow) — GitHub
    then redirects back to our /callback with `installation_id` and the same
    `state`, which we use to know which portal user initiated the connection.
    """
    PermissionService(db).ensure_admin_or_manager(user)
    client = _client_or_400()
    state = create_access_token(str(user.id))
    try:
        install_url = client.install_url()
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GithubConnectResponse(install_url=f"{install_url}?state={state}")


@router.get("/callback")
def callback(
    installation_id: int = Query(...),
    setup_action: str = Query(default="install"),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Public redirect target configured as the GitHub App's Setup URL (see
    docs/github-app-setup.md). Not protected by a bearer token because GitHub
    redirects the user's browser here directly; the `state` JWT (minted in
    /connect) is what ties this back to a portal user. On completion, redirects
    the browser back to the frontend's integrations page (same pattern Vercel
    uses for its GitHub App install flow) so the user sees the result inline
    instead of a bare JSON response.
    """
    settings = get_settings()
    frontend_target = f"{settings.frontend_url}/settings/integrations"

    try:
        client = _client_or_400()
    except HTTPException:
        return RedirectResponse(url=f"{frontend_target}?github=error&reason=not_configured")

    repo = GithubIntegrationRepository(db)

    if setup_action == "request":
        # A repository-selection request pending owner approval; nothing to persist yet.
        return RedirectResponse(url=f"{frontend_target}?github=pending")

    try:
        installation = client.get_installation(installation_id)
    except GithubApiError as exc:
        return RedirectResponse(url=f"{frontend_target}?github=error&reason={exc.status_code}")

    connected_by_user_id = None
    if state:
        try:
            connected_by_user_id = int(decode_token(state)["sub"])
        except Exception:  # noqa: BLE001
            connected_by_user_id = None

    account = installation.get("account", {})
    existing = repo.get_by_installation_id(installation_id)

    if existing:
        existing.account_login = account.get("login", existing.account_login)
        existing.suspended_at = None
        repo.update(existing)
    else:
        repo.create(
            GithubIntegration(
                installation_id=installation_id,
                account_login=account.get("login", "unknown"),
                account_type=account.get("type", "User"),
                connected_by_user_id=connected_by_user_id,
                connected_at=utcnow(),
            )
        )
    return RedirectResponse(url=f"{frontend_target}?github=connected")


@router.delete("/{integration_id}", status_code=204, response_model=None)
def disconnect(integration_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    PermissionService(db).ensure_admin_or_manager(user)
    repo = GithubIntegrationRepository(db)
    integration = repo.get(integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    repo.delete(integration)


@router.get("/{integration_id}/repositories", response_model=list[GithubRepositoryRead])
def list_repositories(
    integration_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[GithubRepositoryRead]:
    PermissionService(db).ensure_admin_or_manager(user)
    installation_id = _resolve_installation_id(db, integration_id)
    client = _client_or_400()
    try:
        repos = client.list_repositories(installation_id)
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return [GithubRepositoryRead(**r.__dict__) for r in repos]


@router.get("/{integration_id}/repositories/{owner}/{repository}/branches", response_model=list[str])
def list_branches(
    integration_id: int,
    owner: str,
    repository: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    PermissionService(db).ensure_admin_or_manager(user)
    installation_id = _resolve_installation_id(db, integration_id)
    client = _client_or_400()
    try:
        return client.list_branches(installation_id, owner, repository)
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{integration_id}/repositories/{owner}/{repository}/discover", response_model=list[dict])
def discover(
    integration_id: int,
    owner: str,
    repository: str,
    payload: GithubDiscoverRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    PermissionService(db).ensure_admin_or_manager(user)
    try:
        service = GithubDiscoveryService(db)
        return service.discover(integration_id, owner, repository, payload.branch)
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{integration_id}/import", response_model=list[AutomationImportPreview])
def import_selected(
    integration_id: int,
    payload: GithubImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AutomationImportPreview]:
    """Stages each selected automation (built + stored, awaiting /automations/import/{staging_id}/confirm)."""
    PermissionService(db).ensure_admin_or_manager(user)
    try:
        service = GithubDiscoveryService(db)
        previews = [
            service.stage_import(
                integration_id, payload.owner, payload.repository, payload.branch, manifest_path, user
            )
            for manifest_path in payload.manifest_paths
        ]
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return [AutomationImportPreview(**p) for p in previews]
