from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.orchestration.api.compat_dispatch import create_and_schedule_execution
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.orchestration.infrastructure.orm.models import LegacyJobMirrorRecord, TriggerCompatRecord
from modules.orchestration.triggers.api.schemas import (
    TriggerCreateRequest,
    TriggerDryRunRequest,
    TriggerDryRunResponse,
    TriggerResponse,
    TriggerUpdateRequest,
)
from modules.orchestration.triggers.domain.mapping import apply_parameter_mapping

router = APIRouter(prefix="/triggers")


@router.get("", response_model=list[TriggerResponse])
def list_triggers(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[TriggerResponse]:
    rows = db.scalars(select(TriggerCompatRecord).order_by(TriggerCompatRecord.created_at.desc())).all()
    return [_trigger_response(row) for row in rows if _can_view_trigger(db, user, row)]


@router.post("", response_model=TriggerResponse, status_code=status.HTTP_201_CREATED)
def create_trigger(
    payload: TriggerCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerResponse:
    ensure_automation_action(db, user, payload.automation_id, "can_create")
    _ensure_source_automation(db, user, payload)
    row = TriggerCompatRecord(**_resolved_trigger_fields(payload))
    db.add(row)
    db.flush()
    _record_audit(db, user, "trigger_created", "trigger", str(row.id), after={"route_path": row.route_path})
    db.commit()
    db.refresh(row)
    return _trigger_response(row)


@router.put("/{trigger_id}", response_model=TriggerResponse)
def update_trigger(
    trigger_id: int,
    payload: TriggerUpdateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerResponse:
    row = _get_trigger_or_404(db, trigger_id)
    ensure_automation_action(db, user, row.automation_id, "can_edit")
    ensure_automation_action(db, user, payload.automation_id, "can_edit")
    _ensure_source_automation(db, user, payload)
    for field, value in _resolved_trigger_fields(payload).items():
        setattr(row, field, value)
    db.add(row)
    db.flush()
    _record_audit(db, user, "trigger_updated", "trigger", str(row.id), after={"route_path": row.route_path})
    db.commit()
    db.refresh(row)
    return _trigger_response(row)


@router.delete(
    "/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_trigger(
    trigger_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> None:
    row = _get_trigger_or_404(db, trigger_id)
    ensure_automation_action(db, user, row.automation_id, "can_delete")
    _record_audit(db, user, "trigger_deleted", "trigger", str(row.id), after={"route_path": row.route_path})
    db.delete(row)
    db.commit()


@router.post("/invoke/{route_path:path}")
def invoke_trigger(
    route_path: str,
    request: Request,
    payload_json: dict[str, Any] | None = Body(default=None),
    x_trigger_secret: str = Header(...),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    job = _dispatch_by_route(
        db,
        route_path=route_path,
        secret_token=x_trigger_secret,
        body=payload_json or {},
        headers=dict(request.headers),
        query_params=dict(request.query_params),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"job_id": job.id}


@router.post("/{trigger_id}/test", response_model=TriggerDryRunResponse)
def test_trigger_mapping(
    trigger_id: int,
    payload: TriggerDryRunRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerDryRunResponse:
    row = _get_trigger_or_404(db, trigger_id)
    ensure_automation_action(db, user, row.automation_id, "can_edit")
    parameters = apply_parameter_mapping(row.parameter_mapping_json, payload.sample_payload, payload.sample_headers, payload.sample_query_params)
    return TriggerDryRunResponse(automation_id=row.automation_id, parameters=parameters)


def dispatch_webhook_trigger(
    db: Session,
    *,
    route_path: str,
    secret_token: str,
    body: dict[str, Any],
    headers: dict[str, Any],
    query_params: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
) -> LegacyJobMirrorRecord:
    return _dispatch_by_route(
        db,
        route_path=route_path,
        secret_token=secret_token,
        body=body,
        headers=headers,
        query_params=query_params,
        ip=ip,
        user_agent=user_agent,
    )


def _dispatch_by_route(
    db: Session,
    *,
    route_path: str,
    secret_token: str,
    body: dict[str, Any],
    headers: dict[str, Any],
    query_params: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
) -> LegacyJobMirrorRecord:
    trigger = db.scalar(
        select(TriggerCompatRecord).where(TriggerCompatRecord.route_path == _normalize_route_path(route_path))
    )
    if trigger is None or not trigger.is_active or trigger.secret_token != secret_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger credentials.")

    catalog = build_catalog_adapters(db).catalog
    automation = catalog.get_automation(trigger.automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    version = catalog.get_latest_published_version(trigger.automation_id)
    if version is None:
        raise HTTPException(status_code=422, detail="Automation does not have a published version.")

    parameters = apply_parameter_mapping(trigger.parameter_mapping_json, body, headers, query_params)
    details = create_and_schedule_execution(
        db,
        automation_version_id=version.id,
        actor=ActorDTO(actor_type="trigger", actor_id=str(trigger.id), ip=ip, user_agent=user_agent),
        parameters=parameters,
        priority=_priority_to_int(automation.default_priority),
        origin="trigger",
    )
    job = LegacyJobMirrorRecord(
        automation_id=trigger.automation_id,
        requested_by_user_id=None,
        trigger_id=trigger.id,
        status="queued",
        priority=automation.default_priority,
        payload_json={
            **parameters,
            "_execution_id": details.execution.id,
            "_task_execution_id": details.tasks[0].id if details.tasks else None,
            "_execution_attempt_id": details.current_attempt.id if details.current_attempt else None,
        },
        assigned_worker_id=(details.agent or {}).get("worker_id") if details.agent else None,
    )
    db.add(job)
    db.flush()
    build_orchestration_adapters(db).executions.link_legacy_job(details.execution.id, job.id)
    _record_audit(
        db,
        ActorDTO(actor_type="trigger", actor_id=str(trigger.id), ip=ip, user_agent=user_agent),
        "trigger_invoked",
        "trigger",
        str(trigger.id),
        after={"route_path": trigger.route_path, "job_id": job.id, "execution_id": details.execution.id},
    )
    db.commit()
    db.refresh(job)
    return job


def _get_trigger_or_404(db: Session, trigger_id: int) -> TriggerCompatRecord:
    row = db.get(TriggerCompatRecord, trigger_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trigger not found.")
    return row


def _can_view_trigger(db: Session, user: Any, row: TriggerCompatRecord) -> bool:
    try:
        ensure_automation_action(db, user, row.automation_id, "can_view")
        return True
    except HTTPException:
        return False


def _ensure_source_automation(db: Session, user: Any, payload: TriggerCreateRequest) -> None:
    if payload.trigger_type == "chained" and payload.source_automation_id is not None:
        ensure_automation_action(db, user, payload.source_automation_id, "can_view")


def _resolved_trigger_fields(payload: TriggerCreateRequest) -> dict[str, Any]:
    data = payload.model_dump()
    if payload.trigger_type == "chained":
        data["route_path"] = f"chain/{uuid.uuid4().hex[:12]}"
        data["secret_token"] = secrets.token_urlsafe(24)
    elif data.get("route_path"):
        data["route_path"] = _normalize_route_path(data["route_path"])
    return data


def _trigger_response(row: TriggerCompatRecord) -> TriggerResponse:
    return TriggerResponse(
        id=row.id,
        automation_id=row.automation_id,
        trigger_type=row.trigger_type,
        route_path=row.route_path,
        secret_token=row.secret_token,
        is_active=row.is_active,
        parameter_mapping_json=row.parameter_mapping_json,
        template=row.template,
        source_automation_id=row.source_automation_id,
        condition=row.condition,
    )


def _record_audit(db: Session, actor: Any, action: str, resource_type: str, resource_id: str, after: dict[str, Any] | None = None) -> None:
    SqlAlchemyAuditEventRepository(db).append(
        AuditEvent(
            id=f"aud_{uuid.uuid4().hex}",
            organization_id=getattr(actor, "organization_id", None),
            actor_type=getattr(actor, "actor_type", "user"),
            actor_id=str(getattr(actor, "id", None) or getattr(actor, "actor_id", None) or "") or None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            after=after,
            ip=getattr(actor, "ip", None),
            user_agent=getattr(actor, "user_agent", None),
            occurred_at=datetime.now(UTC),
        )
    )


def _normalize_route_path(value: str) -> str:
    return str(value).strip().lstrip("/")


def _priority_to_int(priority: str | None) -> int:
    return {
        "critical": 100,
        "high": 50,
        "normal": 0,
        "low": -10,
    }.get(priority or "normal", 0)
