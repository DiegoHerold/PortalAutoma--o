from sqlalchemy.orm import Session

from app.core.constants import JobPriority, JobStatus
from app.core.permissions import is_admin
from app.models.job import Job
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.utils.datetime import utcnow
from modules.catalog.infrastructure.repositories import SqlAlchemyCatalogRepository
from modules.dispatch.application.use_cases import ScheduleTaskExecution
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.application.dto import ActorDTO, CreateAutomationExecutionCommand
from modules.orchestration.application.use_cases import CreateAutomationExecution, GetExecutionDetails, RequestExecutionCancellation
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters


FINAL_JOB_STATUSES = {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED}


class JobNotCancellableError(Exception):
    """Raised when trying to cancel a job that has already reached a final state."""


class JobDispatcherService:
    """
    Thin compatibility adapter for the legacy /jobs API.

    Official scheduling, selection, retry, timeout and cancellation live in
    backend/modules. The Job row is only a frontend compatibility mirror.
    """

    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.automations = AutomationRepository(db)
        self.jobs = JobRepository(db)
        self.permissions = PermissionService(db)

    def dispatch(self, user: User, payload: JobCreate) -> Job:
        self.permissions.ensure_automation_action(user, payload.automation_id, "can_execute")
        automation = self.automations.get(payload.automation_id)
        if not automation:
            raise ValueError("Automation not found")
        version = SqlAlchemyCatalogRepository(self.db).get_latest_published_version(payload.automation_id)
        if version is None:
            raise ValueError("Automation does not have a published version.")
        details = self._create_execution(
            automation_version_id=version.id,
            actor=ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email),
            payload=payload,
            priority=_priority_to_int(payload.priority or automation.default_priority),
            origin="manual",
        )
        return self._materialize_legacy_job(user.id, payload, automation.default_priority, details)

    def dispatch_system(self, payload: JobCreate, schedule_id: int | None = None, trigger_id: int | None = None) -> Job:
        automation = self.automations.get(payload.automation_id)
        if not automation:
            raise ValueError("Automation not found")
        version = SqlAlchemyCatalogRepository(self.db).get_latest_published_version(payload.automation_id)
        if version is None:
            raise ValueError("Automation does not have a published version.")
        details = self._create_execution(
            automation_version_id=version.id,
            actor=ActorDTO(actor_type="system", actor_id=None),
            payload=payload,
            priority=_priority_to_int(payload.priority or automation.default_priority),
            origin="system",
        )
        job = self._materialize_legacy_job(None, payload, automation.default_priority, details)
        job.schedule_id = schedule_id
        job.trigger_id = trigger_id
        self.db.add(job)
        self.db.commit()
        return job

    def _create_execution(self, automation_version_id: int, actor: ActorDTO, payload: JobCreate, priority: int, origin: str):
        adapters = build_orchestration_adapters(self.db)
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
                automation_version_id=automation_version_id,
                actor=actor,
                parameters=payload.payload_json or {},
                priority=priority,
                origin=origin,
            )
        )
        if details.tasks:
            dispatch_adapters = build_dispatch_adapters(self.db)
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
            adapters = build_orchestration_adapters(self.db)
            details = GetExecutionDetails(
                adapters.executions,
                adapters.tasks,
                adapters.attempts,
                adapters.offers,
                adapters.automation_versions,
                adapters.agent_selection,
            ).execute(details.execution.id)
        return details

    def _materialize_legacy_job(self, requested_by_user_id: int | None, payload: JobCreate, default_priority: str, details) -> Job:
        agent = details.agent or {}
        job = Job(
            automation_id=payload.automation_id,
            requested_by_user_id=requested_by_user_id,
            status=JobStatus.QUEUED,
            priority=payload.priority or default_priority,
            payload_json={
                **(payload.payload_json or {}),
                "_execution_id": details.execution.id,
                "_task_execution_id": details.tasks[0].id if details.tasks else None,
                "_execution_attempt_id": details.current_attempt.id if details.current_attempt else None,
            },
            scheduled_for=payload.scheduled_for,
            assigned_worker_id=agent.get("worker_id"),
        )
        job = self.jobs.create(job)
        adapters = build_orchestration_adapters(self.db)
        adapters.executions.link_legacy_job(details.execution.id, job.id)
        self.db.commit()
        return job

    def cancel_job(self, user: User, job_id: int) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError("Job not found.")
        self.permissions.ensure_automation_action(user, job.automation_id, "can_execute")
        if job.status in FINAL_JOB_STATUSES:
            raise JobNotCancellableError(f"Job ja esta em estado final ({job.status}) e nao pode ser cancelado.")

        previous_status = job.status
        execution_id = (job.payload_json or {}).get("_execution_id")
        if execution_id:
            adapters = build_dispatch_adapters(self.db)
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
                actor=ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email),
                reason=f"Cancelado manualmente por {user.email}.",
            )
            job.status = JobStatus.CANCELLED if result.get("status") == "cancelled" else "cancelling"
        else:
            job.status = JobStatus.CANCELLED
            job.finished_at = utcnow()
        job.error_message = f"Cancelado manualmente por {user.email}."
        self.audit.record(
            action="job_cancel_requested",
            actor_email=user.email,
            actor_type="user",
            entity_type="job",
            entity_id=str(job.id),
            details=f"previous_status={previous_status}",
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, user: User) -> list[Job]:
        jobs = self.jobs.list_all()
        if is_admin(user):
            return jobs
        allowed_category_ids = {permission.category_id for permission in user.category_permissions if permission.can_view}
        automation_category_map = {automation.id: automation.category_id for automation in self.automations.list_all()}
        return [job for job in jobs if automation_category_map.get(job.automation_id) in allowed_category_ids]

    def get_job(self, user: User, job_id: int) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError("Job not found.")
        if is_admin(user):
            return job
        automation = self.automations.get(job.automation_id)
        allowed_category_ids = {permission.category_id for permission in user.category_permissions if permission.can_view}
        if automation is None or automation.category_id not in allowed_category_ids:
            raise ValueError("Job not found.")
        return job


def _priority_to_int(priority: str | None) -> int:
    order = {
        JobPriority.CRITICAL: 100,
        JobPriority.HIGH: 50,
        JobPriority.NORMAL: 0,
        JobPriority.LOW: -10,
        "critical": 100,
        "high": 50,
        "normal": 0,
        "low": -10,
    }
    return order.get(priority or JobPriority.NORMAL, 0)
