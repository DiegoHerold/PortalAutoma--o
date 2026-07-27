from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from modules.catalog.api.schemas import (
    AutomationVersionCreateRequest,
    AutomationVersionResponse,
    BlockRequest,
    PackageResponse,
    PackageUploadCreateRequest,
    PackageUploadResponse,
    RuntimeCreateRequest,
    RuntimeResponse,
    RuntimeVersionCreateRequest,
    RuntimeVersionResponse,
)
from modules.catalog.application.dto import ActorDTO
from modules.catalog.application.use_cases import (
    AbortPackageUpload,
    BlockAutomationVersion,
    BlockRuntimeVersion,
    CompletePackageUpload,
    CreateAutomationVersion,
    CreateRuntime,
    CreateRuntimeVersion,
    DeprecateAutomationVersion,
    DeprecateRuntimeVersion,
    GetAutomationVersion,
    GetPackage,
    GetPackageValidation,
    GetRuntime,
    GetRuntimeVersion,
    InitiatePackageUpload,
    ListRuntimes,
    PublishAutomationVersion,
    PublishRuntimeVersion,
    ValidateAutomationVersion,
)
from modules.catalog.domain.errors import CatalogError
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.shared.application.idempotency import IdempotencyRecord, IdempotencyReplayStatus
from modules.shared.infrastructure.repositories import SqlAlchemyIdempotencyStore

router = APIRouter()


@router.post("/automations/{automation_id}/versions", response_model=AutomationVersionResponse, status_code=status.HTTP_201_CREATED)
def create_automation_version(
    automation_id: int,
    payload: AutomationVersionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    replay = _reserve_idempotency(db, "automation-version:create", idempotency_key, {"automation_id": automation_id, **payload.model_dump()})
    if replay is not None:
        return AutomationVersionResponse.model_validate(replay)
    try:
        result = CreateAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            automation_id,
            {
                "release_notes": payload.release_notes,
                "source_repository": payload.source_repository,
                "source_branch": payload.source_branch,
                "source_tag": payload.source_tag,
                "source_commit_sha": payload.source_commit_sha,
                "build_id": payload.build_id,
                "idempotency_key": idempotency_key,
            },
            payload.raw_manifest,
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = AutomationVersionResponse.model_validate(result, from_attributes=True)
    _save_idempotency(db, "automation-version:create", idempotency_key, response.model_dump(mode="json"), str(response.id))
    return response


@router.get("/automation-versions/{version_id}", response_model=AutomationVersionResponse)
def get_automation_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    try:
        result = GetAutomationVersion(adapters.catalog).execute(version_id)
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automation-versions/{version_id}/validate", response_model=AutomationVersionResponse)
def validate_automation_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    try:
        result = ValidateAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(version_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automation-versions/{version_id}/publish", response_model=AutomationVersionResponse)
def publish_automation_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    version = adapters.catalog.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Automation version not found.")
    try:
        result = PublishAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(version.automation_id, version_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automation-versions/{version_id}/deprecate", response_model=AutomationVersionResponse)
def deprecate_automation_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    version = adapters.catalog.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Automation version not found.")
    result = DeprecateAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(version.automation_id, version_id, _actor(user))
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automation-versions/{version_id}/block", response_model=AutomationVersionResponse)
def block_automation_version(
    version_id: int,
    payload: BlockRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutomationVersionResponse:
    adapters = build_catalog_adapters(db)
    version = adapters.catalog.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Automation version not found.")
    result = BlockAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(version.automation_id, version_id, _actor(user), payload.reason)
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automation-versions/{version_id}/package-uploads", response_model=PackageUploadResponse, status_code=status.HTTP_201_CREATED)
def initiate_package_upload(
    version_id: int,
    payload: PackageUploadCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PackageUploadResponse:
    adapters = build_catalog_adapters(db)
    replay = _reserve_idempotency(db, "package-upload:initiate", idempotency_key, {"version_id": version_id, **payload.model_dump()})
    if replay is not None:
        return PackageUploadResponse.model_validate(replay)
    try:
        result = InitiatePackageUpload(
            adapters.catalog,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.temporary_urls,
            adapters.audit,
            adapters.outbox,
            adapters.transaction,
            adapters.packages_bucket_name,
        ).execute(version_id, payload.file_name, payload.expected_size_bytes, payload.expected_sha256, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = PackageUploadResponse.model_validate(result, from_attributes=True)
    _save_idempotency(db, "package-upload:initiate", idempotency_key, response.model_dump(mode="json"), response.id)
    return response


@router.put("/package-uploads/{upload_session_id}/bytes", response_model=PackageResponse)
async def upload_package_bytes(
    upload_session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackageResponse:
    adapters = build_catalog_adapters(db)
    with tempfile.TemporaryDirectory(prefix="package_upload_") as tmp:
        target = Path(tmp) / (file.filename or "package.zip")
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        result = CompletePackageUpload(
            adapters.catalog,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.object_storage,
            adapters.package_validator,
            adapters.audit,
            adapters.outbox,
            adapters.transaction,
            adapters.max_package_size_bytes,
        ).execute(upload_session_id, _actor(user), target)
    return PackageResponse.model_validate(result, from_attributes=True)


@router.post("/package-uploads/{upload_session_id}/complete", response_model=PackageResponse)
def complete_package_upload(
    upload_session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackageResponse:
    adapters = build_catalog_adapters(db)
    try:
        result = CompletePackageUpload(
            adapters.catalog,
            adapters.stored_objects,
            adapters.upload_sessions,
            adapters.object_storage,
            adapters.package_validator,
            adapters.audit,
            adapters.outbox,
            adapters.transaction,
            adapters.max_package_size_bytes,
        ).execute(upload_session_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PackageResponse.model_validate(result, from_attributes=True)


@router.post("/package-uploads/{upload_session_id}/abort", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def abort_package_upload(
    upload_session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    adapters = build_catalog_adapters(db)
    AbortPackageUpload(adapters.upload_sessions, adapters.audit, adapters.transaction).execute(upload_session_id, _actor(user))


@router.get("/packages/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackageResponse:
    adapters = build_catalog_adapters(db)
    result = GetPackage(adapters.catalog).execute(package_id)
    return PackageResponse.model_validate(result, from_attributes=True)


@router.get("/packages/{package_id}/validation")
def get_package_validation(
    package_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    adapters = build_catalog_adapters(db)
    return GetPackageValidation(adapters.catalog).execute(package_id)


@router.get("/runtimes", response_model=list[RuntimeResponse])
def list_runtimes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RuntimeResponse]:
    adapters = build_catalog_adapters(db)
    return [RuntimeResponse.model_validate(item, from_attributes=True) for item in ListRuntimes(adapters.catalog).execute()]


@router.post("/runtimes", response_model=RuntimeResponse, status_code=status.HTTP_201_CREATED)
def create_runtime(
    payload: RuntimeCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RuntimeResponse:
    adapters = build_catalog_adapters(db)
    replay = _reserve_idempotency(db, "runtime:create", idempotency_key, payload.model_dump())
    if replay is not None:
        return RuntimeResponse.model_validate(replay)
    result = CreateRuntime(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
        {**payload.model_dump(), "idempotency_key": idempotency_key},
        _actor(user),
    )
    response = RuntimeResponse.model_validate(result, from_attributes=True)
    _save_idempotency(db, "runtime:create", idempotency_key, response.model_dump(mode="json"), response.id)
    return response


@router.get("/runtimes/{runtime_id}", response_model=RuntimeResponse)
def get_runtime(
    runtime_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuntimeResponse:
    adapters = build_catalog_adapters(db)
    result = GetRuntime(adapters.catalog).execute(runtime_id)
    return RuntimeResponse.model_validate(result, from_attributes=True)


@router.post("/runtimes/{runtime_id}/versions", response_model=RuntimeVersionResponse, status_code=status.HTTP_201_CREATED)
def create_runtime_version(
    runtime_id: str,
    payload: RuntimeVersionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    replay = _reserve_idempotency(db, "runtime-version:create", idempotency_key, {"runtime_id": runtime_id, **payload.model_dump()})
    if replay is not None:
        return RuntimeVersionResponse.model_validate(replay)
    result = CreateRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
        runtime_id,
        {**payload.model_dump(), "idempotency_key": idempotency_key},
        _actor(user),
    )
    response = RuntimeVersionResponse.model_validate(result, from_attributes=True)
    _save_idempotency(db, "runtime-version:create", idempotency_key, response.model_dump(mode="json"), response.id)
    return response


@router.get("/runtime-versions/{runtime_version_id}", response_model=RuntimeVersionResponse)
def get_runtime_version(
    runtime_version_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = GetRuntimeVersion(adapters.catalog).execute(runtime_version_id)
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/publish", response_model=RuntimeVersionResponse)
def publish_runtime_version(
    runtime_version_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = PublishRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user))
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/deprecate", response_model=RuntimeVersionResponse)
def deprecate_runtime_version(
    runtime_version_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = DeprecateRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user))
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/block", response_model=RuntimeVersionResponse)
def block_runtime_version(
    runtime_version_id: str,
    payload: BlockRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = BlockRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user), payload.reason)
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)


def _reserve_idempotency(db: Session, scope: str, key: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not key:
        return None
    store = SqlAlchemyIdempotencyStore(db)
    request_hash = _payload_hash(payload)
    existing = store.get(scope, key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key reused with a different payload.")
        if existing.response_payload is not None:
            return existing.response_payload
    status = store.reserve(IdempotencyRecord(key=key, scope=scope, request_hash=request_hash))
    if status == IdempotencyReplayStatus.CONFLICT:
        raise HTTPException(status_code=409, detail="Idempotency-Key reused with a different payload.")
    return None


def _save_idempotency(db: Session, scope: str, key: str | None, payload: dict[str, Any], resource_id: str | None) -> None:
    if not key:
        return
    SqlAlchemyIdempotencyStore(db).save_response(scope, key, 200, _jsonable(payload), resource_id)
    db.commit()


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
