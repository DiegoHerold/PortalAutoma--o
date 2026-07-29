from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from infrastructure.storage.factory import get_package_storage
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.authentication import JwtTokenIssuer
from modules.catalog.api.schemas import AutomationImportConfirmRequest, AutomationImportPreview, AutomationVersionResponse
from modules.catalog.application.dto import ActorDTO
from modules.catalog.application.use_cases import ConfirmStagedAutomationImport
from modules.catalog.domain.errors import CatalogValidationError, DuplicateAutomationVersionError
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.catalog.infrastructure.import_packaging import AutomationImportPackagingError, CatalogImportPackagingService
from modules.catalog.infrastructure.import_staging_store import delete_staging_entry, get_staging_entry

router = APIRouter()


@router.post("/import/upload", response_model=AutomationImportPreview)
async def import_from_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationImportPreview:
    _ensure_admin_or_manager(db, user)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .zip.")
    try:
        preview = CatalogImportPackagingService(db).import_from_zip(file, user)
    except AutomationImportPackagingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationImportPreview.model_validate(preview)


@router.post("/import/{staging_id}/confirm", response_model=AutomationVersionResponse)
def confirm_import(
    staging_id: str,
    payload: AutomationImportConfirmRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationVersionResponse:
    _ensure_admin_or_manager(db, user)
    staged = get_staging_entry(staging_id)
    if staged is None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Import staging entry not found or expired.")
    adapters = build_catalog_adapters(db)
    try:
        version = ConfirmStagedAutomationImport(
            adapters.catalog,
            adapters.stored_objects,
            adapters.audit,
            adapters.outbox,
            adapters.transaction,
        ).execute(staged, _actor(user), payload.category_id)
    except DuplicateAutomationVersionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CatalogValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    delete_staging_entry(staging_id)
    return AutomationVersionResponse.model_validate(version, from_attributes=True)


@router.delete("/import/{staging_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def discard_import(
    staging_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    _ensure_admin_or_manager(db, user)
    delete_staging_entry(staging_id)


@router.get("/artifacts/download")
def download_artifact(token: str) -> FileResponse:
    try:
        payload = JwtTokenIssuer().decode_package_download_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token de download invalido ou expirado.") from exc

    storage = get_package_storage()
    path = storage.open_local_path(payload["bucket"], payload["object_key"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Pacote nao encontrado.")
    return FileResponse(path, media_type="application/zip", filename="package.zip")


def _actor(user: Any) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)


def _ensure_admin_or_manager(db: Session, user: Any) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_admin_or_manager(user)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
