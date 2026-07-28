from __future__ import annotations

import asyncio
import json
import queue
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.permission_service import PermissionService
from modules.orchestration.application.use_cases import GetExecutionDetails
from modules.orchestration.domain.errors import OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.telemetry.application.dto import to_payload
from modules.telemetry.application.use_cases import (
    GetExecutionEvents,
    GetExecutionLogs,
    GetExecutionMetrics,
    GetExecutionProcesses,
    GetExecutionProgress,
    GetExecutionTimeline,
)
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.realtime import execution_realtime_publisher

router = APIRouter(prefix="/executions")


@router.get("/{execution_id}/events")
def get_execution_events(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = None,
    event_type: str | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    page = GetExecutionEvents(adapters.events).execute(
        execution_id,
        limit=limit,
        cursor=cursor,
        event_type=event_type,
        level=level,
    )
    return to_payload(page)


@router.get("/{execution_id}/timeline")
def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=300, ge=1, le=1000),
    cursor: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionTimeline(adapters.events).execute(execution_id, limit=limit, cursor=cursor))


@router.get("/{execution_id}/logs")
def get_execution_logs(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionLogs(adapters.events).execute(execution_id, limit=limit, cursor=cursor, level=level))


@router.get("/{execution_id}/metrics")
def get_execution_metrics(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=1000),
    metric_name: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionMetrics(adapters.metrics).execute(execution_id, limit=limit, metric_name=metric_name))


@router.get("/{execution_id}/progress")
def get_execution_progress(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionProgress(adapters.events).execute(execution_id))


@router.get("/{execution_id}/processes")
def get_execution_processes(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)
    return to_payload(GetExecutionProcesses(adapters.events).execute(execution_id))


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: str = Query(...),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    user = _user_from_token(db, token)
    _ensure_execution_view(db, user, execution_id)
    adapters = build_telemetry_adapters(db)

    async def event_stream():
        for missed in adapters.events.list_events_after_id(execution_id, last_event_id, limit=500):
            yield _sse("execution.event", {"type": "execution.event", "event": to_payload(missed)}, event_id=missed.id)
        progress = GetExecutionProgress(adapters.events).execute(execution_id)
        yield _sse("execution.progress", {"type": "execution.progress", "progress": to_payload(progress)})
        with execution_realtime_publisher.subscribe(execution_id) as subscription:
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.to_thread(subscription.get, True, 15)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                event = payload.get("event") if isinstance(payload, dict) else None
                event_id = event.get("id") if isinstance(event, dict) else None
                yield _sse(str(payload.get("type") or "execution.update"), payload, event_id=event_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _ensure_execution_view(db: Session, user: User, execution_id: str):
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
        PermissionService(db).ensure_automation_action(user, details.automation_version.automation_id, "can_view")
    return details


def _user_from_token(db: Session, token: str) -> User:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials.")
    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    user = UserRepository(db).get(int(subject))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def _sse(event: str, payload: dict[str, Any], event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False, default=str)}")
    return "\n".join(lines) + "\n\n"
