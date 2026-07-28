from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from modules.dispatch.api.schemas import RetryTaskRequest
from modules.dispatch.application.dto import to_payload
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.application.use_cases import ScheduleTaskRetry

router = APIRouter()


@router.get("/dispatch/queue")
def get_dispatch_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100,
) -> dict[str, Any]:
    adapters = build_dispatch_adapters(db)
    items = adapters.ready_tasks.claim_ready(datetime.utcnow(), min(limit, 200))
    adapters.transaction.rollback()
    return {"items": [to_payload(item) for item in items]}


@router.get("/dispatch/decisions/{decision_id}")
def get_dispatch_decision(
    decision_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    decision = build_dispatch_adapters(db).decisions.get(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Dispatch decision not found.")
    return to_payload(decision)


@router.get("/executions/{execution_id}/dispatch")
def get_execution_dispatch(
    execution_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_dispatch_adapters(db)
    decisions = adapters.decisions.list_for_execution(execution_id)
    return {"execution_id": execution_id, "decisions": [to_payload(item) for item in decisions]}


@router.get("/execution-attempts/{attempt_id}/lease")
def get_attempt_lease(
    attempt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    lease = build_dispatch_adapters(db).leases.active_for_attempt(attempt_id)
    if lease is None:
        return {"execution_attempt_id": attempt_id, "lease": None}
    return {"execution_attempt_id": attempt_id, "lease": to_payload(lease)}


@router.get("/execution-attempts/{attempt_id}/reservations")
def get_attempt_reservations(
    attempt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    reservations = build_dispatch_adapters(db).reservations.list_for_attempt(attempt_id)
    return {"execution_attempt_id": attempt_id, "reservations": [to_payload(item) for item in reservations]}


@router.get("/execution-attempts/{attempt_id}/locks")
def get_attempt_locks(
    attempt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    locks = build_dispatch_adapters(db).locks.list_for_attempt(attempt_id)
    return {"execution_attempt_id": attempt_id, "locks": [to_payload(item) for item in locks]}


@router.post("/task-executions/{task_execution_id}/retry")
def retry_task_execution(
    task_execution_id: str,
    payload: RetryTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    adapters = build_dispatch_adapters(db)
    task = adapters.tasks.get(task_execution_id)
    if task is None:
        raise HTTPException(status_code=404, detail="TaskExecution not found.")
    attempts = [attempt for attempt in adapters.attempts.list_for_execution(task.execution_id) if attempt.task_execution_id == task_execution_id]
    source_attempt_id = payload.source_attempt_id or (attempts[-1].id if attempts else None)
    if source_attempt_id is None:
        raise HTTPException(status_code=409, detail="TaskExecution has no source attempt to retry.")
    try:
        return to_payload(
            ScheduleTaskRetry(
                adapters.tasks,
                adapters.attempts,
                adapters.retry_schedules,
                adapters.outbox,
                adapters.transaction,
            ).execute(
                task_execution_id=task_execution_id,
                source_attempt_id=source_attempt_id,
                reason=payload.reason,
                error_code=payload.error_code,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
