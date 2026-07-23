from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.core.security import decode_package_download_token
from app.integrations.storage.factory import get_package_storage
from app.models.user import User
from app.schemas.automation_import import AutomationImportConfirmRequest, AutomationImportPreview, AutomationVersionRead
from app.services.automation_import_service import (
    AutomationImportService,
    DuplicateVersionError,
    StagingNotFoundError,
)
from app.services.manual_upload_service import ManualUploadError, ManualUploadService
from app.services.permission_service import PermissionService

router = APIRouter()


@router.post("/import/upload", response_model=AutomationImportPreview)
async def import_from_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationImportPreview:
    PermissionService(db).ensure_admin_or_manager(user)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .zip.")
    try:
        preview = ManualUploadService(db).import_from_zip(file, user)
    except ManualUploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationImportPreview(**preview)


@router.post("/import/{staging_id}/confirm", response_model=AutomationVersionRead)
def confirm_import(
    staging_id: str,
    payload: AutomationImportConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionRead:
    PermissionService(db).ensure_admin_or_manager(user)
    try:
        version = AutomationImportService(db).confirm(staging_id, user, payload.category_id)
    except StagingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except DuplicateVersionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationVersionRead.model_validate(version)


@router.delete("/import/{staging_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def discard_import(
    staging_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    PermissionService(db).ensure_admin_or_manager(user)
    AutomationImportService(db).discard(staging_id)


@router.get("/artifacts/download")
def download_artifact(token: str) -> FileResponse:
    """
    Signed, time-limited download used by the Automation Agent when
    STORAGE_BACKEND=local (with S3/MinIO, the agent gets a real presigned URL
    directly and never hits this endpoint).
    """
    try:
        payload = decode_package_download_token(token)
    except Exception as exc:  # noqa: BLE001 - jose raises several exception types
        raise HTTPException(status_code=401, detail="Token de download inválido ou expirado.") from exc

    storage = get_package_storage()
    path = storage.open_local_path(payload["bucket"], payload["object_key"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Pacote não encontrado.")
    return FileResponse(path, media_type="application/zip", filename="package.zip")
