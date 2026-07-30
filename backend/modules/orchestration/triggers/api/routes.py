from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.fleet.domain.value_objects import hash_secret, secrets_match
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.orchestration.api.compat_dispatch import create_and_schedule_execution
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.orchestration.infrastructure.orm.models import (
    LegacyJobMirrorRecord,
    OrchestrationExecutionRecord,
    TriggerCompatRecord,
)
from modules.orchestration.triggers.api.schemas import (
    TriggerCreateRequest,
    TriggerCreateResponse,
    TriggerDryRunRequest,
    TriggerDryRunResponse,
    TriggerResponse,
    TriggerRotateSecretResponse,
    TriggerUpdateRequest,
)
from modules.orchestration.triggers.domain.mapping import apply_parameter_mapping

router = APIRouter(prefix="/triggers")

_ROUTE_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_RESERVED_ROUTE_PATHS = {"api", "github", "invoke", "trigger", "webhooks"}
_REDACTED_SECRET_PLACEHOLDER = "__redacted__"
_rate_limiter: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 120
_MAX_PAYLOAD_BYTES = 1024 * 1024


@router.get("/config")
def trigger_config(_user: Any = Depends(get_current_user)) -> dict[str, str]:
    base = get_settings().backend_public_url.rstrip("/")
    return {
        "backend_public_url": base,
        "invoke_base_url": f"{base}/api/v1/triggers/invoke",
        "method": "POST",
        "required_header": "X-Trigger-Secret",
    }


@router.get("", response_model=list[TriggerResponse])
def list_triggers(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[TriggerResponse]:
    rows = db.scalars(select(TriggerCompatRecord).order_by(TriggerCompatRecord.created_at.desc())).all()
    return [_trigger_response(db, row) for row in rows if _can_view_trigger(db, user, row)]


@router.get("/{trigger_id}", response_model=TriggerResponse)
def get_trigger(
    trigger_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerResponse:
    row = _get_trigger_or_404(db, trigger_id)
    ensure_automation_action(db, user, row.automation_id, "can_view")
    return _trigger_response(db, row)


@router.post("", response_model=TriggerCreateResponse, status_code=status.HTTP_201_CREATED)
def create_trigger(
    payload: TriggerCreateRequest,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerCreateResponse:
    ensure_automation_action(db, user, payload.automation_id, "can_create")
    _ensure_source_automation(db, user, payload)
    secret_token = payload.secret_token or _generate_webhook_secret()
    fields = _resolved_trigger_fields(payload, secret_token=secret_token)
    _ensure_unique_route_path(db, fields["route_path"])
    row = TriggerCompatRecord(**fields)
    db.add(row)
    db.flush()
    _record_audit(db, user, "trigger_created", "trigger", str(row.id), after={"route_path": row.route_path})
    db.commit()
    db.refresh(row)
    response = _trigger_response(db, row)
    return TriggerCreateResponse(**response.model_dump(), secret_token=secret_token if row.trigger_type == "https" else None)


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
    fields = _resolved_trigger_update_fields(payload)
    _ensure_unique_route_path(db, fields["route_path"], exclude_id=row.id)
    for field, value in fields.items():
        setattr(row, field, value)
    db.add(row)
    db.flush()
    _record_audit(db, user, "trigger_updated", "trigger", str(row.id), after={"route_path": row.route_path})
    db.commit()
    db.refresh(row)
    return _trigger_response(db, row)


@router.post("/{trigger_id}/rotate-secret", response_model=TriggerRotateSecretResponse)
def rotate_trigger_secret(
    trigger_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> TriggerRotateSecretResponse:
    row = _get_trigger_or_404(db, trigger_id)
    ensure_automation_action(db, user, row.automation_id, "can_edit")
    if row.trigger_type != "https":
        raise HTTPException(status_code=409, detail="Only HTTP webhooks have a rotatable secret.")
    secret_token = _generate_webhook_secret()
    now = datetime.now(UTC)
    row.secret_hash = hash_secret(secret_token)
    row.secret_last_four = secret_token[-4:]
    row.secret_rotated_at = now
    row.secret_created_at = row.secret_created_at or now
    row.secret_token = _REDACTED_SECRET_PLACEHOLDER
    db.add(row)
    db.flush()
    _record_audit(db, user, "trigger_secret_rotated", "trigger", str(row.id), after={"route_path": row.route_path})
    db.commit()
    return TriggerRotateSecretResponse(secret_token=secret_token, created_at=now, previous_secret_revoked=True, secret_last_four=row.secret_last_four)


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
    affected_jobs = db.scalar(select(LegacyJobMirrorRecord.id).where(LegacyJobMirrorRecord.trigger_id == row.id).limit(1)) is not None
    db.execute(update(LegacyJobMirrorRecord).where(LegacyJobMirrorRecord.trigger_id == row.id).values(trigger_id=None))
    _record_audit(db, user, "trigger_deleted", "trigger", str(row.id), after={"route_path": row.route_path, "legacy_jobs_unlinked": affected_jobs})
    db.delete(row)
    db.commit()


@router.post("/invoke/{route_path:path}")
def invoke_trigger(
    route_path: str,
    request: Request,
    payload_json: dict[str, Any] | None = Body(default=None),
    x_trigger_secret: str = Header(...),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    _validate_public_invocation_request(request)
    correlation_id = _correlation_id(x_correlation_id)
    job = _dispatch_by_route(
        db,
        route_path=route_path,
        secret_token=x_trigger_secret,
        body=payload_json or {},
        headers=dict(request.headers),
        query_params=dict(request.query_params),
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    payload = job.payload_json or {}
    return {"success": True, "job_id": job.id, "execution_id": payload.get("_execution_id"), "correlation_id": correlation_id}


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
    errors = _mapping_errors(row.parameter_mapping_json, parameters)
    return TriggerDryRunResponse(automation_id=row.automation_id, parameters=parameters, valid=not errors, errors=errors)


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
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
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
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
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
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
) -> LegacyJobMirrorRecord:
    trigger = db.scalar(select(TriggerCompatRecord).where(TriggerCompatRecord.route_path == _normalize_route_path(route_path)))
    if trigger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found.")
    if not trigger.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook is inactive.")
    if not _secret_matches(trigger, secret_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger credentials.")

    catalog = build_catalog_adapters(db).catalog
    automation = catalog.get_automation(trigger.automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    version = catalog.get_latest_published_version(trigger.automation_id)
    if version is None:
        raise HTTPException(status_code=422, detail="Automation does not have a published version.")

    parameters = apply_parameter_mapping(trigger.parameter_mapping_json, body, headers, query_params)
    scoped_idempotency_key = f"trigger:{trigger.id}:{idempotency_key}" if idempotency_key else None
    details = create_and_schedule_execution(
        db,
        automation_version_id=version.id,
        actor=ActorDTO(actor_type="trigger", actor_id=str(trigger.id), ip=ip, user_agent=user_agent),
        parameters=parameters,
        priority=_priority_to_int(automation.default_priority),
        origin="trigger",
        correlation_id=correlation_id,
        idempotency_key=scoped_idempotency_key,
        request_hash=_payload_hash({"trigger_id": trigger.id, "parameters": parameters}),
    )
    if details.execution.legacy_job_id:
        existing = db.get(LegacyJobMirrorRecord, details.execution.legacy_job_id)
        if existing is not None:
            return existing
    job = LegacyJobMirrorRecord(
        automation_id=trigger.automation_id,
        requested_by_user_id=None,
        trigger_id=trigger.id,
        status="queued",
        priority=automation.default_priority,
        payload_json={
            **parameters,
            "_trigger_id": trigger.id,
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


def _ensure_source_automation(db: Session, user: Any, payload: TriggerCreateRequest | TriggerUpdateRequest) -> None:
    if payload.trigger_type == "chained" and payload.source_automation_id is not None:
        ensure_automation_action(db, user, payload.source_automation_id, "can_view")


def _resolved_trigger_fields(payload: TriggerCreateRequest, *, secret_token: str) -> dict[str, Any]:
    data = payload.model_dump(exclude={"secret_token"})
    data["name"] = (payload.name or payload.route_path or "Webhook").strip()
    if payload.trigger_type == "chained":
        data["route_path"] = f"chain/{uuid.uuid4().hex[:12]}"
    else:
        data["route_path"] = _normalize_route_path(str(payload.route_path))
    data["secret_hash"] = hash_secret(secret_token)
    data["secret_last_four"] = secret_token[-4:]
    data["secret_created_at"] = datetime.now(UTC)
    data["secret_rotated_at"] = None
    data["secret_token"] = _REDACTED_SECRET_PLACEHOLDER
    return data


def _resolved_trigger_update_fields(payload: TriggerUpdateRequest) -> dict[str, Any]:
    data = payload.model_dump()
    data["name"] = (payload.name or payload.route_path or "Webhook").strip()
    if payload.trigger_type == "chained":
        data["route_path"] = data.get("route_path") or f"chain/{uuid.uuid4().hex[:12]}"
    else:
        data["route_path"] = _normalize_route_path(str(payload.route_path))
    return data


def _trigger_response(db: Session, row: TriggerCompatRecord) -> TriggerResponse:
    latest_job = _latest_trigger_job(db, row.id)
    latest_execution: OrchestrationExecutionRecord | None = None
    if latest_job and (latest_job.payload_json or {}).get("_execution_id"):
        latest_execution = db.get(OrchestrationExecutionRecord, str((latest_job.payload_json or {}).get("_execution_id")))
    return TriggerResponse(
        id=row.id,
        name=row.name or row.route_path,
        automation_id=row.automation_id,
        trigger_type=row.trigger_type,
        route_path=row.route_path,
        is_active=row.is_active,
        parameter_mapping_json=row.parameter_mapping_json,
        template=row.template,
        source_automation_id=row.source_automation_id,
        condition=row.condition,
        secret_configured=bool(row.secret_hash or row.secret_token),
        secret_last_four=row.secret_last_four or (row.secret_token[-4:] if row.secret_token and row.secret_token != _REDACTED_SECRET_PLACEHOLDER else None),
        secret_created_at=row.secret_created_at,
        secret_rotated_at=row.secret_rotated_at,
        invocation_url=_invocation_url(row.route_path) if row.trigger_type == "https" else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_invoked_at=latest_job.created_at if latest_job else None,
        last_execution_id=latest_execution.id if latest_execution else None,
        last_execution_status=latest_execution.status if latest_execution else latest_job.status if latest_job else None,
        last_execution_duration_seconds=_duration_seconds(latest_execution),
    )


def _latest_trigger_job(db: Session, trigger_id: int) -> LegacyJobMirrorRecord | None:
    return db.scalar(
        select(LegacyJobMirrorRecord)
        .where(LegacyJobMirrorRecord.trigger_id == trigger_id)
        .order_by(LegacyJobMirrorRecord.created_at.desc())
        .limit(1)
    )


def _secret_matches(row: TriggerCompatRecord, candidate: str) -> bool:
    if row.secret_hash:
        return secrets_match(candidate, row.secret_hash)
    return secrets.compare_digest(candidate, row.secret_token or "")


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
    normalized = str(value).strip().strip("/")
    if not normalized:
        raise HTTPException(status_code=422, detail="route_path nao pode ser vazio.")
    if any(char.isspace() for char in normalized) or "\\" in normalized or "//" in normalized or ".." in normalized:
        raise HTTPException(status_code=422, detail="route_path contem caracteres invalidos.")
    if not _ROUTE_PATH_RE.match(normalized):
        raise HTTPException(status_code=422, detail="route_path deve usar letras, numeros, ponto, traco, underscore ou barras simples.")
    if normalized.split("/", 1)[0] in _RESERVED_ROUTE_PATHS:
        raise HTTPException(status_code=422, detail="route_path usa prefixo reservado.")
    return normalized


def _ensure_unique_route_path(db: Session, route_path: str, exclude_id: int | None = None) -> None:
    existing = db.scalar(select(TriggerCompatRecord).where(TriggerCompatRecord.route_path == route_path))
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(status_code=409, detail="route_path ja esta em uso.")


def _generate_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _invocation_url(route_path: str) -> str:
    base = get_settings().backend_public_url.rstrip("/")
    return f"{base}/api/v1/triggers/invoke/{route_path}"


def _duration_seconds(execution: OrchestrationExecutionRecord | None) -> float | None:
    if execution is None or not execution.started_at or not execution.completed_at:
        return None
    return max(0.0, (execution.completed_at - execution.started_at).total_seconds())


def _mapping_errors(mapping: dict[str, str] | None, parameters: dict[str, Any]) -> list[str]:
    if not mapping:
        return []
    return [f"{name}: caminho '{path}' nao encontrado." for name, path in mapping.items() if parameters.get(name) is None]


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    _rate_limiter[client_ip] = [timestamp for timestamp in _rate_limiter[client_ip] if now - timestamp < _RATE_LIMIT_WINDOW_SECONDS]
    if len(_rate_limiter[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
        return False
    _rate_limiter[client_ip].append(now)
    return True


def _validate_public_invocation_request(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
        if size > _MAX_PAYLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    content_type = request.headers.get("content-type")
    if content_type and "application/json" not in content_type.lower():
        raise HTTPException(status_code=415, detail="Webhook endpoint accepts application/json payloads.")


def _correlation_id(value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned:
        return cleaned[:120]
    return f"corr_{uuid.uuid4().hex}"


def _priority_to_int(priority: str | None) -> int:
    return {
        "critical": 100,
        "high": 50,
        "normal": 0,
        "low": -10,
    }.get(priority or "normal", 0)
