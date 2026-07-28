from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.api.authorization import ensure_automation_action
from modules.dispatch.application.use_cases import ScheduleTaskExecution
from modules.dispatch.domain.errors import AgentSelectionError, DispatchError
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.api.schemas import (
    ExecutionCreateRequest,
    ExecutionDetailsResponse,
    ExecutionResponse,
    ExecutionSummaryResponse,
)
from modules.orchestration.application.dto import ActorDTO, CreateAutomationExecutionCommand
from modules.orchestration.application.use_cases import CreateAutomationExecution, GetExecutionDetails, ListExecutions, ListExecutionSummaries, RequestExecutionCancellation
from modules.orchestration.domain.errors import AutomationVersionNotExecutable, IdempotencyConflict, OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.storage.infrastructure.adapters import build_storage_adapters
from modules.telemetry.application.dto import to_payload as telemetry_payload
from modules.telemetry.application.use_cases import GetTelemetrySummary
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters

router = APIRouter(prefix="/executions")


@router.post("", response_model=ExecutionDetailsResponse, status_code=status.HTTP_201_CREATED)
def create_execution(
    payload: ExecutionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ExecutionDetailsResponse:
    adapters = build_orchestration_adapters(db)
    version_id = _version_id(payload.automation_version_id)
    snapshot = adapters.automation_versions.get_published_snapshot(version_id)
    if snapshot is None:
        raise HTTPException(status_code=400, detail="AutomationVersion must be published and have published package/runtime.")
    ensure_automation_action(db, user, snapshot.automation_id, "can_execute")
    command_payload = {
        "automation_version_id": version_id,
        "agent_id": payload.agent_id,
        "parameters": payload.parameters,
        "priority": payload.priority,
    }
    try:
        details = CreateAutomationExecution(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.offers,
            adapters.automation_versions,
            adapters.agent_selection,
            adapters.commands,
            adapters.outbox,
            adapters.audit,
            adapters.idempotency,
            adapters.transaction,
        ).execute(
            CreateAutomationExecutionCommand(
                automation_version_id=version_id,
                actor=_actor(user, request),
                parameters=payload.parameters,
                priority=payload.priority,
                agent_id=payload.agent_id,
                origin="manual",
                idempotency_key=idempotency_key,
                request_hash=_payload_hash(command_payload),
            )
        )
        if details.tasks:
            dispatch_adapters = build_dispatch_adapters(db)
            ScheduleTaskExecution(
                dispatch_adapters.ready_tasks,
                dispatch_adapters.attempts,
                dispatch_adapters.offers,
                dispatch_adapters.automation_versions,
                dispatch_adapters.candidates,
                dispatch_adapters.decisions,
                dispatch_adapters.reservations,
                dispatch_adapters.locks,
                dispatch_adapters.commands,
                dispatch_adapters.outbox,
                dispatch_adapters.transaction,
            ).execute(details.tasks[0].id)
            adapters = build_orchestration_adapters(db)
            details = GetExecutionDetails(
                adapters.executions,
                adapters.tasks,
                adapters.attempts,
                adapters.offers,
                adapters.automation_versions,
                adapters.agent_selection,
            ).execute(details.execution.id)
        return ExecutionDetailsResponse.model_validate(details.to_payload())
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AutomationVersionNotExecutable, AgentSelectionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OrchestrationError, DispatchError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionSummaryResponse])
def list_executions(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
) -> list[ExecutionSummaryResponse]:
    adapters = build_orchestration_adapters(db)
    summaries = ListExecutionSummaries(
        adapters.executions,
        adapters.tasks,
        adapters.attempts,
        adapters.automation_versions,
        adapters.agent_selection,
    ).execute(limit=limit, offset=offset)
    return [ExecutionSummaryResponse.model_validate(item.to_payload()) for item in summaries]


@router.get("/{execution_id}/tasks")
def list_execution_tasks(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    details = _details_for_user(db, user, execution_id)
    return [_jsonable(asdict(item)) for item in details.tasks]


@router.get("/{execution_id}/attempts")
def list_execution_attempts(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    details = _details_for_user(db, user, execution_id)
    return [_jsonable(asdict(item)) for item in details.attempts]


@router.post("/{execution_id}/cancel")
def cancel_execution(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    details = _details_for_user(db, user, execution_id)
    if details.automation_version is not None:
        ensure_automation_action(db, user, details.automation_version.automation_id, "can_execute")
    dispatch_adapters = build_dispatch_adapters(db)
    try:
        return _jsonable(
            RequestExecutionCancellation(
                dispatch_adapters.executions,
                dispatch_adapters.tasks,
                dispatch_adapters.attempts,
                dispatch_adapters.cancellation_requests,
                dispatch_adapters.commands,
                dispatch_adapters.reservations,
                dispatch_adapters.locks,
                dispatch_adapters.leases,
                dispatch_adapters.outbox,
                dispatch_adapters.transaction,
            ).execute(
                execution_id,
                actor=_actor(user, request),
                reason=(payload or {}).get("reason") if isinstance(payload, dict) else None,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{execution_id}", response_model=ExecutionDetailsResponse)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> ExecutionDetailsResponse:
    details = _details_for_user(db, user, execution_id)
    payload = details.to_payload()
    telemetry_adapters = build_telemetry_adapters(db)
    storage_adapters = build_storage_adapters(db)
    payload["telemetry"] = telemetry_payload(
        GetTelemetrySummary(telemetry_adapters.events, telemetry_adapters.metrics).execute(
            execution_id,
            artifact_count=storage_adapters.artifacts.count_for_execution(execution_id),
        )
    )
    return ExecutionDetailsResponse.model_validate(payload)


def _details_for_user(db: Session, user: Any, execution_id: str):
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


def _actor(user: Any, request: Request) -> ActorDTO:
    return ActorDTO(
        actor_type="user",
        actor_id=str(user.id),
        actor_email=user.email,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _version_id(value: int | str) -> int:
    if isinstance(value, int):
        return value
    candidate = value.removeprefix("av_")
    if candidate.isdigit():
        return int(candidate)
    raise HTTPException(status_code=422, detail="automation_version_id must be an integer id.")


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
