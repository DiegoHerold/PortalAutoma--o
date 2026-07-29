from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import ensure_automation_action
from modules.access.api.dependencies import get_current_user
from modules.catalog.infrastructure.adapters import build_catalog_adapters
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.fleet.infrastructure.orm.models import FleetWorkerRecord
from modules.orchestration.api.compat_dispatch import create_and_schedule_execution
from modules.orchestration.api.schemas import JobCreateRequest, JobResponse
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.application.use_cases import RequestExecutionCancellation
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.orchestration.infrastructure.orm.models import LegacyJobMirrorRecord

router = APIRouter(prefix="/jobs")

FINAL_JOB_STATUSES = {"success", "failed", "cancelled"}


@router.get("", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> list[JobResponse]:
    rows = db.scalars(select(LegacyJobMirrorRecord).order_by(LegacyJobMirrorRecord.created_at.desc())).all()
    return [_job_response(db, row) for row in rows if _can_view_job(db, user, row)]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> JobResponse:
    job = _get_job_or_404(db, job_id)
    if not _can_view_job(db, user, job):
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_response(db, job)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def dispatch_job(
    payload: JobCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> JobResponse:
    ensure_automation_action(db, user, payload.automation_id, "can_execute")
    catalog = build_catalog_adapters(db).catalog
    automation = catalog.get_automation(payload.automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    version = catalog.get_latest_published_version(payload.automation_id)
    if version is None:
        raise HTTPException(status_code=422, detail="Automation does not have a published version.")
    details = create_and_schedule_execution(
        db,
        automation_version_id=version.id,
        actor=_actor(user, request),
        parameters=payload.payload_json or {},
        priority=_priority_to_int(payload.priority or automation.default_priority),
        origin="manual",
    )
    job = LegacyJobMirrorRecord(
        automation_id=payload.automation_id,
        requested_by_user_id=int(user.id),
        status="queued",
        priority=payload.priority or automation.default_priority,
        payload_json={
            **(payload.payload_json or {}),
            "_execution_id": details.execution.id,
            "_task_execution_id": details.tasks[0].id if details.tasks else None,
            "_execution_attempt_id": details.current_attempt.id if details.current_attempt else None,
        },
        scheduled_for=payload.scheduled_for,
        assigned_worker_id=(details.agent or {}).get("worker_id") if details.agent else None,
    )
    db.add(job)
    db.flush()
    build_orchestration_adapters(db).executions.link_legacy_job(details.execution.id, job.id)
    db.commit()
    db.refresh(job)
    return _job_response(db, job)


@router.post("/{job_id}:cancel", response_model=JobResponse)
def cancel_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
) -> JobResponse:
    job = _get_job_or_404(db, job_id)
    ensure_automation_action(db, user, job.automation_id, "can_execute")
    if job.status in FINAL_JOB_STATUSES:
        raise HTTPException(status_code=409, detail=f"Job ja esta em estado final ({job.status}) e nao pode ser cancelado.")
    execution_id = (job.payload_json or {}).get("_execution_id")
    if execution_id:
        adapters = build_dispatch_adapters(db)
        result = RequestExecutionCancellation(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.cancellation_requests,
            adapters.commands,
            adapters.reservations,
            adapters.locks,
            adapters.leases,
            adapters.outbox,
            adapters.transaction,
        ).execute(
            str(execution_id),
            actor=_actor(user, request),
            reason=f"Cancelado manualmente por {user.email}.",
        )
        job.status = "cancelled" if result.get("status") == "cancelled" else "cancelling"
    else:
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
    job.error_message = f"Cancelado manualmente por {user.email}."
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_response(db, job)


def _get_job_or_404(db: Session, job_id: int) -> LegacyJobMirrorRecord:
    job = db.get(LegacyJobMirrorRecord, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _can_view_job(db: Session, user: Any, job: LegacyJobMirrorRecord) -> bool:
    try:
        ensure_automation_action(db, user, job.automation_id, "can_view")
        return True
    except HTTPException:
        return False


def _job_response(db: Session, job: LegacyJobMirrorRecord) -> JobResponse:
    catalog = build_catalog_adapters(db).catalog
    automation = catalog.get_automation(job.automation_id)
    worker = db.get(FleetWorkerRecord, job.assigned_worker_id) if job.assigned_worker_id else None
    return JobResponse(
        id=job.id,
        automation_id=job.automation_id,
        requested_by_user_id=job.requested_by_user_id,
        status=job.status,
        priority=job.priority,
        payload_json=job.payload_json,
        scheduled_for=job.scheduled_for,
        assigned_worker_id=job.assigned_worker_id,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        created_at=job.created_at,
        automation_name=automation.name if automation else None,
        worker_name=worker.name if worker else None,
    )


def _actor(user: Any, request: Request) -> ActorDTO:
    return ActorDTO(
        actor_type="user",
        actor_id=str(user.id),
        actor_email=user.email,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _priority_to_int(priority: str | None) -> int:
    return {
        "critical": 100,
        "high": 50,
        "normal": 0,
        "low": -10,
    }.get(priority or "normal", 0)
