import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.automation import AutomationCreate, AutomationRead, AutomationUpdate
from app.schemas.automation_import import AutomationSourceRead, AutomationVersionRead
from app.schemas.worker_preference import WorkerPreferenceResponse, WorkerPreferenceUpdate
from app.services.automation_service import AutomationHasActiveJobsError, AutomationService
from app.services.automation_version_lifecycle_service import AutomationVersionLifecycleService
from app.services.worker_preference_service import WorkerPreferenceService
from modules.shared.application.idempotency import IdempotencyRecord, IdempotencyReplayStatus
from modules.shared.infrastructure.repositories import SqlAlchemyIdempotencyStore
from modules.catalog.domain.errors import DuplicateAutomationKeyError

router = APIRouter()


@router.get("", response_model=list[AutomationRead])
def list_automations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[AutomationRead]:
    return AutomationService(db).list_automations(current_user)


@router.get("/{automation_id}", response_model=AutomationRead)
def get_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationRead:
    try:
        return AutomationService(db).get_automation(current_user, automation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
def create_automation(
    payload: AutomationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AutomationRead:
    replay = _reserve_idempotency(db, "automation:create", idempotency_key, payload.model_dump())
    if replay is not None:
        return AutomationRead.model_validate(replay)
    try:
        result = AutomationService(db).create_automation(current_user, payload)
    except DuplicateAutomationKeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = AutomationRead.model_validate(result, from_attributes=True)
    _save_idempotency(db, "automation:create", idempotency_key, response.model_dump(mode="json"), str(response.id))
    return response


@router.put("/{automation_id}", response_model=AutomationRead)
def update_automation(
    automation_id: int,
    payload: AutomationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationRead:
    try:
        return AutomationService(db).update_automation(current_user, automation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_automation(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        AutomationService(db).delete_automation(current_user, automation_id)
    except AutomationHasActiveJobsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{automation_id}/worker-preferences", response_model=list[WorkerPreferenceResponse])
def get_worker_preferences(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[WorkerPreferenceResponse]:
    """Get worker preferences for an automation."""
    try:
        automation = AutomationService(db).get_automation(current_user, automation_id)
        return WorkerPreferenceService(db).get_for_automation(automation_id, automation.category_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{automation_id}/worker-preferences", response_model=list[WorkerPreferenceResponse])
def update_worker_preferences(
    automation_id: int,
    payload: WorkerPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[WorkerPreferenceResponse]:
    """Update worker preferences for an automation."""
    try:
        automation = AutomationService(db).get_automation(current_user, automation_id)
        return WorkerPreferenceService(db).replace_for_automation(
            current_user, automation_id, automation.category_id, payload.preferences
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{automation_id}/sources", response_model=list[AutomationSourceRead])
def list_automation_sources(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[AutomationSourceRead]:
    try:
        AutomationService(db).get_automation(current_user, automation_id)  # 404 + permission check
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationVersionLifecycleService(db).list_sources(automation_id)


@router.get("/{automation_id}/versions", response_model=list[AutomationVersionRead])
def list_automation_versions(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[AutomationVersionRead]:
    try:
        AutomationService(db).get_automation(current_user, automation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationVersionLifecycleService(db).list_versions(automation_id)


@router.post("/{automation_id}/versions/{version_id}:activate", response_model=AutomationVersionRead)
def activate_version(
    automation_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationVersionRead:
    automation = AutomationService(db).get_automation(current_user, automation_id)
    from app.services.permission_service import PermissionService

    PermissionService(db).ensure_category_action(current_user, automation.category_id, "can_edit")
    try:
        return AutomationVersionLifecycleService(db).activate(automation_id, version_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{automation_id}/versions/{version_id}:deprecate", response_model=AutomationVersionRead)
def deprecate_version(
    automation_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AutomationVersionRead:
    automation = AutomationService(db).get_automation(current_user, automation_id)
    from app.services.permission_service import PermissionService

    PermissionService(db).ensure_category_action(current_user, automation.category_id, "can_edit")
    try:
        return AutomationVersionLifecycleService(db).deprecate(automation_id, version_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{automation_id}:sync")
def sync_automation_source(
    automation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    """
    Re-checks the automation's GitHub source for a newer commit affecting its
    path, without importing anything automatically (section 16). Requires the
    GitHub App to be configured and the automation to have a github source.
    """
    automation = AutomationService(db).get_automation(current_user, automation_id)
    from app.services.permission_service import PermissionService

    PermissionService(db).ensure_category_action(current_user, automation.category_id, "can_view")
    try:
        return AutomationVersionLifecycleService(db).check_for_update(automation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _reserve_idempotency(db: Session, scope: str, key: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not key:
        return None
    store = SqlAlchemyIdempotencyStore(db)
    request_hash = _payload_hash(payload)
    existing = store.get(scope, key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key reutilizada com payload diferente.")
        if existing.response_payload is not None:
            return existing.response_payload
    status = store.reserve(IdempotencyRecord(key=key, scope=scope, request_hash=request_hash))
    if status == IdempotencyReplayStatus.CONFLICT:
        raise HTTPException(status_code=409, detail="Idempotency-Key reutilizada com payload diferente.")
    return None


def _save_idempotency(db: Session, scope: str, key: str | None, payload: dict[str, Any], resource_id: str | None) -> None:
    if not key:
        return
    SqlAlchemyIdempotencyStore(db).save_response(scope, key, 201, _jsonable(payload), resource_id)
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
