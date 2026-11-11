from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from infrastructure.github import GithubApiError, GithubAppClient, GithubAppNotConfiguredError
from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain.times import efetivas
from modules.access.domain import AuthorizationDenied, RoleSlug
from modules.access.infrastructure.adapters import build_access_adapters
from modules.catalog.api.schemas import (
    AutomationCreateRequest,
    AutomationResponse,
    AutomationSourceResponse,
    AutomationSyncResponse,
    AutomationUpdateRequest,
    AutomationVersionCreateRequest,
    AutomationVersionResponse,
    BlockRequest,
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    PackageResponse,
    PackageUploadCreateRequest,
    PackageUploadResponse,
    RuntimeCreateRequest,
    RuntimeResponse,
    RuntimeVersionCreateRequest,
    RuntimeVersionResponse,
    WorkerPreferenceResponse,
    WorkerPreferenceUpdateRequest,
)
from modules.catalog.application.dto import ActorDTO, RuntimeDTO, RuntimeVersionDTO
from modules.catalog.application.use_cases import (
    AbortPackageUpload,
    ArchiveAutomation,
    RestoreAutomation,
    ArchiveCategory,
    CreateAutomation,
    BlockAutomationVersion,
    BlockRuntimeVersion,
    CompletePackageUpload,
    CreateCategory,
    CreateAutomationVersion,
    CreateRuntime,
    CreateRuntimeVersion,
    DeprecateAutomationVersion,
    DeprecateRuntimeVersion,
    GetAutomation,
    GetAutomationVersion,
    GetCategory,
    GetPackage,
    GetPackageValidation,
    GetRuntime,
    GetRuntimeVersion,
    InitiatePackageUpload,
    ListAutomations,
    ListRuntimes,
    ListRuntimeVersions,
    ListAutomationVersions,
    ListCategories,
    PublishAutomationVersion,
    PublishRuntimeVersion,
    UpdateAutomationMetadata,
    UpdateCategory,
    ValidateAutomationVersion,
)
from modules.catalog.domain.errors import CatalogError
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.fleet.application.use_cases import GetAutomationWorkerPreferences, ReplaceAutomationWorkerPreferences
from modules.fleet.infrastructure.repositories import SqlAlchemyAutomationWorkerPreferenceRepository
from modules.governance.domain.audit import AuditEvent
from modules.governance.application.use_cases import ListSystemLimits
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.shared.application.idempotency import IdempotencyRecord, IdempotencyReplayStatus
from modules.shared.infrastructure.repositories import SqlAlchemyIdempotencyStore
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus

router = APIRouter()


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[CategoryResponse]:
    adapters = build_catalog_adapters(db)
    categories = ListCategories(adapters.catalog).execute()
    if _is_admin(user):
        return [CategoryResponse.model_validate(item, from_attributes=True) for item in categories]
    allowed_category_ids = _allowed_category_ids(user, "can_view")
    return [
        CategoryResponse.model_validate(item, from_attributes=True)
        for item in categories
        if item.id in allowed_category_ids
    ]


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> CategoryResponse:
    adapters = build_catalog_adapters(db)
    try:
        category = GetCategory(adapters.catalog).execute(category_id)
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not _is_admin(user) and category.id not in _allowed_category_ids(user, "can_view"):
        raise HTTPException(status_code=404, detail="Category not found.")
    return CategoryResponse.model_validate(category, from_attributes=True)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> CategoryResponse:
    adapters = build_catalog_adapters(db)
    _ensure_admin_or_manager(db, user)
    try:
        category = CreateCategory(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            payload.model_dump(),
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CategoryResponse.model_validate(category, from_attributes=True)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> CategoryResponse:
    adapters = build_catalog_adapters(db)
    _ensure_admin_or_manager(db, user)
    try:
        category = UpdateCategory(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            category_id,
            payload.model_dump(),
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CategoryResponse.model_validate(category, from_attributes=True)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def archive_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    adapters = build_catalog_adapters(db)
    _ensure_admin_or_manager(db, user)
    try:
        ArchiveCategory(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(category_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/automations", response_model=list[AutomationResponse])
def list_automations(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AutomationResponse]:
    adapters = build_catalog_adapters(db)
    automations = ListAutomations(adapters.catalog).execute()
    if _is_admin(user):
        return [AutomationResponse.model_validate(item, from_attributes=True) for item in automations]
    allowed_category_ids = _allowed_category_ids(user, "can_view")
    return [
        AutomationResponse.model_validate(item, from_attributes=True)
        for item in automations
        if item.category_id in allowed_category_ids
    ]


@router.get("/automations/{automation_id}", response_model=AutomationResponse)
def get_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationResponse:
    adapters = build_catalog_adapters(db)
    try:
        automation = GetAutomation(adapters.catalog).execute(automation_id)
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not _is_admin(user):
        ensure_automation_action(db, user, automation_id, "can_view")
    return AutomationResponse.model_validate(automation, from_attributes=True)


@router.post("/automations", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
def create_automation(
    payload: AutomationCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AutomationResponse:
    adapters = build_catalog_adapters(db)
    _ensure_category_action(db, user, payload.category_id, "can_create")
    payload_data = payload.model_dump()
    if not payload_data.get("key"):
        payload_data["key"] = payload_data.get("slug")
    replay = _reserve_idempotency(db, "automation:create", idempotency_key, payload_data)
    if replay is not None:
        return AutomationResponse.model_validate(replay)
    try:
        result = CreateAutomation(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            {**payload_data, "idempotency_key": idempotency_key},
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response = AutomationResponse.model_validate(result, from_attributes=True)
    _save_idempotency(db, "automation:create", idempotency_key, response.model_dump(mode="json"), str(response.id))
    return response


@router.put("/automations/{automation_id}", response_model=AutomationResponse)
def update_automation(
    automation_id: int,
    payload: AutomationUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationResponse:
    adapters = build_catalog_adapters(db)
    category_id = ensure_automation_action(db, user, automation_id, "can_edit")
    _ensure_category_action(db, user, category_id, "can_edit")
    try:
        result = UpdateAutomationMetadata(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            automation_id,
            payload.model_dump(),
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationResponse.model_validate(result, from_attributes=True)


@router.delete("/automations/{automation_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def archive_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    adapters = build_catalog_adapters(db)
    ensure_automation_action(db, user, automation_id, "can_delete")
    try:
        ArchiveAutomation(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(automation_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/automations/{automation_id}/restaurar", response_model=AutomationResponse)
def restore_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationResponse:
    adapters = build_catalog_adapters(db)
    ensure_automation_action(db, user, automation_id, "can_delete")
    try:
        result = RestoreAutomation(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            automation_id, _actor(user))
    except CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationResponse.model_validate(result, from_attributes=True)


@router.get("/automations/{automation_id}/sources", response_model=list[AutomationSourceResponse])
def list_automation_sources(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AutomationSourceResponse]:
    ensure_automation_action(db, user, automation_id, "can_view")
    adapters = build_catalog_adapters(db)
    return [
        AutomationSourceResponse.model_validate(item, from_attributes=True)
        for item in adapters.catalog.list_sources(automation_id)
    ]


@router.get("/automations/{automation_id}/versions", response_model=list[AutomationVersionResponse])
def list_automation_versions(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[AutomationVersionResponse]:
    ensure_automation_action(db, user, automation_id, "can_view")
    adapters = build_catalog_adapters(db)
    return [
        AutomationVersionResponse.model_validate(item, from_attributes=True)
        for item in ListAutomationVersions(adapters.catalog).execute(automation_id)
    ]


@router.get("/automations/{automation_id}/worker-preferences", response_model=list[WorkerPreferenceResponse])
def get_worker_preferences(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[WorkerPreferenceResponse]:
    ensure_automation_action(db, user, automation_id, "can_view")
    preferences = GetAutomationWorkerPreferences(SqlAlchemyAutomationWorkerPreferenceRepository(db)).execute(automation_id)
    return [WorkerPreferenceResponse.model_validate(item, from_attributes=True) for item in preferences]


@router.put("/automations/{automation_id}/worker-preferences", response_model=list[WorkerPreferenceResponse])
def update_worker_preferences(
    automation_id: int,
    payload: WorkerPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[WorkerPreferenceResponse]:
    ensure_automation_action(db, user, automation_id, "can_edit")
    preferences = ReplaceAutomationWorkerPreferences(SqlAlchemyAutomationWorkerPreferenceRepository(db)).execute(
        automation_id,
        [item.model_dump() for item in payload.preferences],
    )
    build_catalog_adapters(db).audit.append(
        AuditEvent(
            id=str(uuid4()),
            actor_type="user",
            actor_id=str(user.id),
            action="automation.worker_preferences_updated",
            resource_type="automation",
            resource_id=str(automation_id),
            after={"preference_count": len(preferences)},
        )
    )
    db.commit()
    return [WorkerPreferenceResponse.model_validate(item, from_attributes=True) for item in preferences]


@router.post("/automations/{automation_id}:sync", response_model=AutomationSyncResponse)
def sync_automation_source(
    automation_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationSyncResponse:
    ensure_automation_action(db, user, automation_id, "can_view")
    adapters = build_catalog_adapters(db)
    source = adapters.catalog.get_active_source(automation_id)
    if source is None or source.type != "github":
        raise HTTPException(status_code=400, detail="Esta automacao nao possui uma origem GitHub configurada.")
    if source.integration_id is None or not source.owner or not source.repository or not source.branch or not source.automation_path:
        raise HTTPException(status_code=422, detail="Origem GitHub da automacao esta incompleta.")
    client: GithubAppClient | None = None
    try:
        client = GithubAppClient()
        latest_commit = client.get_latest_commit_for_path(
            source.integration_id,
            source.owner,
            source.repository,
            source.branch,
            source.automation_path,
        )
    except GithubAppNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GithubApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        if client is not None:
            client.close()
    current_version = adapters.catalog.get_latest_published_version(automation_id)
    update_available = bool(latest_commit) and latest_commit != source.last_commit_sha
    adapters.catalog.update_source(source.id, {"sync_status": "update_available" if update_available else "synced"})
    db.commit()
    return AutomationSyncResponse(
        update_available=update_available,
        current_commit=source.last_commit_sha,
        latest_commit=latest_commit,
        current_version=current_version.version if current_version else None,
    )


@router.post("/automations/{automation_id}/versions/{version_id}:activate", response_model=AutomationVersionResponse)
def activate_automation_version_alias(
    automation_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationVersionResponse:
    ensure_automation_action(db, user, automation_id, "can_approve")
    adapters = build_catalog_adapters(db)
    try:
        result = PublishAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            automation_id,
            version_id,
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automations/{automation_id}/versions/{version_id}:deprecate", response_model=AutomationVersionResponse)
def deprecate_automation_version_alias(
    automation_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> AutomationVersionResponse:
    ensure_automation_action(db, user, automation_id, "can_approve")
    adapters = build_catalog_adapters(db)
    try:
        result = DeprecateAutomationVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(
            automation_id,
            version_id,
            _actor(user),
        )
    except CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AutomationVersionResponse.model_validate(result, from_attributes=True)


@router.post("/automations/{automation_id}/versions", response_model=AutomationVersionResponse, status_code=status.HTTP_201_CREATED)
def create_automation_version(
    automation_id: int,
    payload: AutomationVersionCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PackageUploadResponse:
    adapters = build_catalog_adapters(db)
    max_bytes = _system_limit_bytes(db, "package.max_size_mb", get_settings().max_upload_size_mb)
    if payload.expected_size_bytes is not None and payload.expected_size_bytes > max_bytes:
        raise HTTPException(status_code=422, detail="Package exceeds the configured maximum size.")
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


@router.put("/package-uploads/{upload_session_id}/bytes", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def upload_package_bytes(
    upload_session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    adapters = build_catalog_adapters(db)
    upload_session = adapters.upload_sessions.get(upload_session_id)
    if upload_session is None:
        raise HTTPException(status_code=404, detail="Upload session not found.")
    if upload_session.status in {UploadSessionStatus.COMPLETED, UploadSessionStatus.ABORTED, UploadSessionStatus.EXPIRED}:
        raise HTTPException(status_code=422, detail=f"Upload session is already {upload_session.status}.")
    stored_object = adapters.stored_objects.get(upload_session.stored_object_id)
    if stored_object is None:
        raise HTTPException(status_code=422, detail="Stored object not found.")
    with tempfile.TemporaryDirectory(prefix="package_upload_") as tmp:
        target = Path(tmp) / (file.filename or "package.zip")
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        max_bytes = _system_limit_bytes(db, "package.max_size_mb", get_settings().max_upload_size_mb)
        if target.stat().st_size > max_bytes:
            raise HTTPException(status_code=422, detail="Package exceeds the configured maximum size.")
        uploaded_object = adapters.object_storage.put_file(
            stored_object.bucket,
            stored_object.object_key,
            target,
            stored_object.content_type,
        )
    adapters.stored_objects.update(
        StoredObject(
            id=stored_object.id,
            bucket=uploaded_object.bucket,
            object_key=uploaded_object.object_key,
            content_type=uploaded_object.content_type,
            size_bytes=uploaded_object.size_bytes,
            sha256=uploaded_object.sha256,
            etag=uploaded_object.etag,
            provider=uploaded_object.provider,
            status=StoredObjectStatus.UPLOADED,
            created_at=stored_object.created_at,
            verified_at=stored_object.verified_at,
            deleted_at=stored_object.deleted_at,
        )
    )
    adapters.upload_sessions.update(
        UploadSession(
            id=upload_session.id,
            stored_object_id=upload_session.stored_object_id,
            upload_url=upload_session.upload_url,
            status=UploadSessionStatus.UPLOADING,
            expected_size_bytes=upload_session.expected_size_bytes,
            expected_sha256=upload_session.expected_sha256,
            created_by=upload_session.created_by,
            created_at=upload_session.created_at,
            expires_at=upload_session.expires_at,
        )
    )
    adapters.transaction.commit()


@router.post("/package-uploads/{upload_session_id}/complete", response_model=PackageResponse)
def complete_package_upload(
    upload_session_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
) -> None:
    adapters = build_catalog_adapters(db)
    AbortPackageUpload(adapters.upload_sessions, adapters.audit, adapters.transaction).execute(upload_session_id, _actor(user))


@router.get("/packages/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> PackageResponse:
    adapters = build_catalog_adapters(db)
    result = GetPackage(adapters.catalog).execute(package_id)
    return PackageResponse.model_validate(result, from_attributes=True)


@router.get("/packages/{package_id}/validation")
def get_package_validation(
    package_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> dict:
    adapters = build_catalog_adapters(db)
    return GetPackageValidation(adapters.catalog).execute(package_id)


@router.get("/runtimes", response_model=list[RuntimeResponse])
def list_runtimes(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[RuntimeResponse]:
    adapters = build_catalog_adapters(db)
    return [
        _runtime_response(item, adapters.catalog.list_runtime_versions(item.id))
        for item in ListRuntimes(adapters.catalog).execute()
    ]


@router.post("/runtimes", response_model=RuntimeResponse, status_code=status.HTTP_201_CREATED)
def create_runtime(
    payload: RuntimeCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
) -> RuntimeResponse:
    adapters = build_catalog_adapters(db)
    result = GetRuntime(adapters.catalog).execute(runtime_id)
    return _runtime_response(result, ListRuntimeVersions(adapters.catalog).execute(runtime_id))


@router.post("/runtimes/{runtime_id}/versions", response_model=RuntimeVersionResponse, status_code=status.HTTP_201_CREATED)
def create_runtime_version(
    runtime_id: str,
    payload: RuntimeVersionCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
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
    user: Any = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = GetRuntimeVersion(adapters.catalog).execute(runtime_version_id)
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/publish", response_model=RuntimeVersionResponse)
def publish_runtime_version(
    runtime_version_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = PublishRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user))
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/deprecate", response_model=RuntimeVersionResponse)
def deprecate_runtime_version(
    runtime_version_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = DeprecateRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user))
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


@router.post("/runtime-versions/{runtime_version_id}/block", response_model=RuntimeVersionResponse)
def block_runtime_version(
    runtime_version_id: str,
    payload: BlockRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> RuntimeVersionResponse:
    adapters = build_catalog_adapters(db)
    result = BlockRuntimeVersion(adapters.catalog, adapters.audit, adapters.outbox, adapters.transaction).execute(runtime_version_id, _actor(user), payload.reason)
    return RuntimeVersionResponse.model_validate(result, from_attributes=True)


def _system_limit_bytes(db: Session, key: str, fallback_megabytes: int) -> int:
    limits = ListSystemLimits(build_governance_adapters(db).governance).execute()
    configured = next((item.value for item in limits if item.key == key and item.organization_id is None), fallback_megabytes)
    return max(0, int(configured)) * 1024 * 1024


def _actor(user: Any) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)


def _runtime_response(runtime: RuntimeDTO, versions: list[RuntimeVersionDTO]) -> RuntimeResponse:
    response = RuntimeResponse.model_validate(runtime, from_attributes=True)
    return response.model_copy(
        update={
            "versions": [
                RuntimeVersionResponse.model_validate(version, from_attributes=True)
                for version in versions
            ]
        }
    )


def _is_admin(user: Any) -> bool:
    role = getattr(user, "role", None)
    return getattr(role, "slug", None) == RoleSlug.ADMIN.value


def _allowed_category_ids(user: Any, action: str) -> set[int]:
    return {
        int(permission.category_id)
        for permission in efetivas(getattr(user, "category_permissions", []) or [],
                                   getattr(user, "team_category_permissions", []) or [])
        if bool(getattr(permission, action, False))
    }


def _ensure_admin_or_manager(db: Session, user: Any) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_admin_or_manager(user)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _ensure_category_action(db: Session, user: Any, category_id: int, action: str) -> None:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_category_action(user, category_id, action)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


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
