from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.authorization import ensure_automation_action, ensure_permission
from modules.orchestration.application.use_cases import GetExecutionDetails
from modules.orchestration.domain.errors import OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.storage.api.schemas import (
    CompleteArtifactUploadRequest,
    FailArtifactUploadRequest,
    InitiateArtifactUploadRequest,
)
from modules.storage.application.dto import (
    CompleteArtifactUploadCommand,
    FailArtifactUploadCommand,
    InitiateArtifactUploadCommand,
    StoreUploadedArtifactBytesCommand,
    to_payload,
)
from modules.storage.application.use_cases import (
    CompleteArtifactUpload,
    FailArtifactUpload,
    GetArtifact,
    InitiateArtifactUpload,
    ListArtifacts,
    ListExecutionArtifacts,
    StoreUploadedArtifactBytes,
)
from modules.storage.domain.errors import ArtifactNotFound, ArtifactSecurityError, ArtifactValidationError, StorageError
from modules.storage.infrastructure.adapters import build_storage_adapters
from modules.storage.domain.states import ArtifactStatus

router = APIRouter()


@router.post("/artifacts/initiate-upload", status_code=status.HTTP_201_CREATED)
def initiate_artifact_upload(
    payload: InitiateArtifactUploadRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_storage_adapters(db)
    context = adapters.attempts.get_context(payload.execution_attempt_id)
    if context is None:
        raise HTTPException(status_code=404, detail="ExecutionAttempt not found.")
    _ensure_execution_view(db, user, context.execution_id)
    max_bytes = _system_limit_bytes(db, "artifact.max_size_mb", get_settings().max_upload_size_mb)
    if payload.size_bytes is not None and payload.size_bytes > max_bytes:
        raise HTTPException(status_code=422, detail="Artifact exceeds the configured maximum size.")
    try:
        result = InitiateArtifactUpload(
            adapters.artifacts,
            adapters.artifact_uploads,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.attempts,
            adapters.object_storage,
            adapters.temporary_urls,
            adapters.transaction,
        ).execute(
            InitiateArtifactUploadCommand(
                execution_attempt_id=payload.execution_attempt_id,
                name=payload.name,
                content_type=payload.content_type,
                size_bytes=payload.size_bytes,
                sha256=payload.sha256,
                metadata=payload.metadata,
                artifact_id=payload.artifact_id,
                created_by=str(user.id),
            )
        )
        return to_payload(result)
    except StorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/artifacts/uploads/{upload_session_id}/bytes")
async def upload_artifact_bytes(
    upload_session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    max_bytes = _system_limit_bytes(db, "artifact.max_size_mb", get_settings().max_upload_size_mb)
    content_type = request.headers.get("content-type") or "application/octet-stream"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="artifact_upload_", delete=False) as tmp:
            temp_path = Path(tmp.name)
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Artifact upload is too large.")
                tmp.write(chunk)
        adapters = build_storage_adapters(db)
        artifact = StoreUploadedArtifactBytes(
            adapters.artifacts,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.object_storage,
            adapters.transaction,
        ).execute(StoreUploadedArtifactBytesCommand(upload_session_id=upload_session_id, file_path=temp_path, content_type=content_type))
        return {"ok": True, "artifact": to_payload(artifact)}
    except StorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


@router.post("/artifacts/{artifact_id}/complete")
def complete_artifact_upload(
    artifact_id: str,
    payload: CompleteArtifactUploadRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_storage_adapters(db)
    artifact = _artifact_for_user(db, user, adapters, artifact_id)
    try:
        completed = CompleteArtifactUpload(
            adapters.artifacts,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.attempts,
            adapters.object_storage,
            adapters.transaction,
        ).execute(
            CompleteArtifactUploadCommand(
                artifact_id=artifact.id,
                execution_attempt_id=payload.execution_attempt_id,
                upload_session_id=payload.upload_session_id,
                size_bytes=payload.size_bytes,
                sha256=payload.sha256,
            )
        )
        return to_payload(completed)
    except ArtifactValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/artifacts/{artifact_id}/fail")
def fail_artifact_upload(
    artifact_id: str,
    payload: FailArtifactUploadRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_storage_adapters(db)
    artifact = _artifact_for_user(db, user, adapters, artifact_id)
    try:
        failed = FailArtifactUpload(
            adapters.artifacts,
            adapters.upload_sessions,
            adapters.attempts,
            adapters.transaction,
        ).execute(
            FailArtifactUploadCommand(
                artifact_id=artifact.id,
                execution_attempt_id=payload.execution_attempt_id,
                upload_session_id=payload.upload_session_id,
                reason=payload.reason,
            )
        )
        return to_payload(failed)
    except StorageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/artifacts")
def list_artifacts(
    execution_id: str | None = None,
    artifact_status: str | None = Query(None, alias="status"),
    search: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    ensure_permission(db, user, "artifact.read")
    adapters = build_storage_adapters(db)
    candidates = ListArtifacts(adapters.artifacts).execute(
        execution_id=execution_id,
        status=artifact_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    visible = []
    for artifact in candidates:
        try:
            _ensure_execution_view(db, user, artifact.execution_id)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                continue
            raise
        visible.append(artifact)
    return to_payload(visible)


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_storage_adapters(db)
    artifact = _artifact_for_user(db, user, adapters, artifact_id)
    return to_payload(artifact)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    adapters = build_storage_adapters(db)
    artifact = _artifact_for_user(db, user, adapters, artifact_id)
    if artifact.status != ArtifactStatus.AVAILABLE.value:
        raise HTTPException(status_code=409, detail="Artifact is not available.")
    stored_object = adapters.stored_objects.get(artifact.stored_object_id or "")
    if stored_object is None:
        raise HTTPException(status_code=404, detail="StoredObject not found.")
    if get_settings().storage_backend == "s3":
        return RedirectResponse(adapters.object_storage.get_download_url(stored_object.bucket, stored_object.object_key))
    path = adapters.object_storage.open_local_path(stored_object.bucket, stored_object.object_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact bytes not found.")
    return FileResponse(path, media_type=artifact.content_type, filename=artifact.name)


@router.get("/executions/{execution_id}/artifacts")
def list_execution_artifacts(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_storage_adapters(db)
    return to_payload(ListExecutionArtifacts(adapters.artifacts).execute(execution_id))


def _artifact_for_user(db: Session, user: Any, adapters, artifact_id: str):
    try:
        artifact = GetArtifact(adapters.artifacts).execute(artifact_id)
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _ensure_execution_view(db, user, artifact.execution_id)
    return artifact


def _ensure_execution_view(db: Session, user: Any, execution_id: str):
    adapters = build_orchestration_adapters(db)
    try:
        details = GetExecutionDetails(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.offers,
            adapters.automation_versions,
            adapters.agent_selection,
        ).execute(execution_id)
    except OrchestrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if details.automation_version is not None:
        ensure_automation_action(db, user, details.automation_version.automation_id, "can_view")
    return details


def _system_limit_bytes(db: Session, key: str, fallback_megabytes: int) -> int:
    """Limite do catálogo de configurações (sem linha gravada, vale o padrão do catálogo)."""
    from modules.governance.infrastructure.limites import ler_limite_em_bytes

    return ler_limite_em_bytes(db, key)
