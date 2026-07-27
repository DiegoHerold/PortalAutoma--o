from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.constants import JobStatus, JobPriority
from app.core.config import get_settings
from app.core.permissions import is_admin
from app.models.job import Job
from app.models.log import ExecutionLog
from app.models.user import User
from app.models.automation_worker_preference import AutomationWorkerPreference
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_worker_preference_repository import AutomationWorkerPreferenceRepository
from app.repositories.job_repository import JobRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas.job import JobCreate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.utils.datetime import utcnow
from modules.catalog.infrastructure.repositories import SqlAlchemyCatalogRepository
from modules.orchestration.application.dto import ActorDTO, CreateAutomationExecutionCommand
from modules.orchestration.application.use_cases import CreateAutomationExecution
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters

FINAL_JOB_STATUSES = {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED}


class JobNotCancellableError(Exception):
    """Raised when trying to cancel a job that has already reached a final state."""


class JobDispatcherService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.settings = get_settings()
        self.automations = AutomationRepository(db)
        self.jobs = JobRepository(db)
        self.workers = WorkerRepository(db)
        self.preferences = AutomationWorkerPreferenceRepository(db)
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

    def dispatch_system(
        self, payload: JobCreate, schedule_id: int | None = None, trigger_id: int | None = None
    ) -> Job:
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
        return CreateAutomationExecution(
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

    def _try_dispatch_job(self, job: Job) -> None:
        """
        Try to assign a worker and dispatch the job.
        If no worker is available, set status to QUEUED.
        """
        # Get worker preferences for this automation
        preferences = self.preferences.get_active_by_automation(job.automation_id)
        
        # Try each worker in preference order
        for pref in preferences:
            worker = self.workers.get(pref.worker_id)
            if worker and self._is_worker_available(worker):
                # Assign to the external Automation Agent queue. The agent
                # WebSocket gateway will promote it to running when delivered.
                job.status = JobStatus.QUEUED
                job.assigned_worker_id = worker.id
                
                self.audit.record(
                    action="job_queued",
                    actor_email=None,
                    actor_type="system",
                    entity_type="job",
                    entity_id=str(job.id),
                    details=f"queued for worker {worker.name}",
                )
                return
        
        # No worker available - set to QUEUED
        job.status = JobStatus.QUEUED
        
        # If no preferences defined, try any compatible worker (fallback behavior)
        if not preferences:
            available_workers = [w for w in self.workers.list_all() if self._is_worker_available(w)]
            if available_workers:
                worker = available_workers[0]
                job.status = JobStatus.QUEUED
                job.assigned_worker_id = worker.id
                
                self.audit.record(
                    action="job_queued",
                    actor_email=None,
                    actor_type="system", 
                    entity_type="job",
                    entity_id=str(job.id),
                    details=f"queued for worker {worker.name} (no preferences)",
                )

    def _is_worker_available(self, worker) -> bool:
        """Check if a worker is available to take a new job."""
        if not worker.is_active:
            return False
        
        if worker.status != "online":
            return False
        
        # Check heartbeat recency
        if worker.last_heartbeat_at:
            heartbeat_window = timedelta(seconds=self.settings.worker_heartbeat_window_seconds)
            now = datetime.now(worker.last_heartbeat_at.tzinfo)
            if now - worker.last_heartbeat_at > heartbeat_window:
                return False
        else:
            return False
        
        # Check current load
        running_jobs = self.db.query(Job).filter(
            and_(
                Job.assigned_worker_id == worker.id,
                Job.status == JobStatus.RUNNING,
            )
        ).count()
        
        return running_jobs < worker.max_concurrency

    def promote_next_job(self, worker_id: int) -> Job | None:
        """
        Find and promote the next queued job for the given worker.
        Called when a job finishes to process the queue.
        """
        worker = self.workers.get(worker_id)
        if not worker or not self._is_worker_available(worker):
            return None
        
        # Get all queued jobs that prefer this worker
        preferences = self.preferences.get_active_by_automation(None)  # Get all preferences
        automation_ids_for_worker = [
            p.automation_id for p in preferences if p.worker_id == worker_id
        ]
        
        # Priority order: critical > high > normal > low, then FIFO by created_at
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3,
        }
        
        # Get queued jobs for automations that prefer this worker
        if automation_ids_for_worker:
            queued_jobs = self.db.query(Job).filter(
                and_(
                    Job.status == JobStatus.QUEUED,
                    Job.automation_id.in_(automation_ids_for_worker),
                )
            ).all()
        else:
            # If no preferences, get any queued jobs (fallback)
            queued_jobs = self.db.query(Job).filter(
                Job.status == JobStatus.QUEUED
            ).all()
        
        if not queued_jobs:
            return None
        
        # Sort by priority then created_at
        queued_jobs.sort(
            key=lambda j: (priority_order.get(j.priority, 999), j.created_at)
        )
        
        next_job = queued_jobs[0]
        
        # Assign to the external agent queue. Delivery happens over WebSocket.
        next_job.status = JobStatus.QUEUED
        next_job.assigned_worker_id = worker_id
        
        self.audit.record(
            action="job_assigned",
            actor_email=None,
            actor_type="system",
            entity_type="job",
            entity_id=str(next_job.id),
            details=f"assigned from queue to worker {worker_id}",
        )
        
        self.db.commit()
        return next_job

    def cancel_job(self, user: User, job_id: int) -> Job:
        """
        Cancel a job that hasn't finished yet (pending/queued/running).

        For pending/queued jobs this simply removes them from the queue. For a
        running job there is no live "abort" channel to the Automation Agent
        today, so this is best-effort: it marks the job (and any associated
        execution) as cancelled on the Portal side, which frees up the worker's
        counted capacity immediately and stops the Portal from waiting on it.
        If the agent is genuinely still running the process in the background,
        it will simply have nowhere to report back to once it finishes.
        """
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError("Job not found.")
        self.permissions.ensure_automation_action(user, job.automation_id, "can_execute")

        if job.status in FINAL_JOB_STATUSES:
            raise JobNotCancellableError(
                f"Job já está em estado final ({job.status}) e não pode ser cancelado."
            )

        now = utcnow()
        previous_status = job.status
        job.status = JobStatus.CANCELLED
        job.started_at = job.started_at or now
        job.finished_at = now
        job.error_message = f"Cancelado manualmente por {user.email}."

        for execution in job.executions:
            if execution.execution_status not in {"success", "failed", "cancelled"}:
                execution.execution_status = "cancelled"
                execution.finished_at = now
                execution.result_summary = job.error_message
                self.db.add(
                    ExecutionLog(
                        execution_id=execution.id,
                        level="WARNING",
                        message=f"Execução cancelada manualmente por {user.email}.",
                    )
                )

        self.audit.record(
            action="job_cancelled",
            actor_email=user.email,
            actor_type="user",
            entity_type="job",
            entity_id=str(job.id),
            details=f"previous_status={previous_status}",
        )
        self.db.commit()
        self.db.refresh(job)
        try:
            from app.services.realtime_service import RealtimeService

            RealtimeService(self.db).emit_job_update(job)
        except Exception:
            pass
        return job

    def list_jobs(self, user: User) -> list[Job]:
        jobs = self.jobs.list_all()
        if is_admin(user):
            return jobs

        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        automation_category_map = {
            automation.id: automation.category_id for automation in self.automations.list_all()
        }
        return [
            job
            for job in jobs
            if automation_category_map.get(job.automation_id) in allowed_category_ids
        ]

    def get_job(self, user: User, job_id: int) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError("Job not found.")
        if is_admin(user):
            return job
        automation = self.automations.get(job.automation_id)
        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        if automation is None or automation.category_id not in allowed_category_ids:
            raise ValueError("Job not found.")
        return job

    def get_queue_position(self, job: Job) -> int | None:
        """Calculate the position of a queued job in its worker's queue."""
        if job.status != JobStatus.QUEUED or not job.assigned_worker_id:
            return None
        
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3,
        }
        
        # Get all queued jobs for the same worker
        queued_jobs = self.db.query(Job).filter(
            and_(
                Job.status == JobStatus.QUEUED,
                Job.assigned_worker_id == job.assigned_worker_id,
            )
        ).all()
        
        # Sort by priority then created_at
        queued_jobs.sort(
            key=lambda j: (priority_order.get(j.priority, 999), j.created_at)
        )
        
        # Find position (1-based)
        for idx, queued_job in enumerate(queued_jobs, start=1):
            if queued_job.id == job.id:
                return idx
        
        return None

    def get_jobs_ahead(self, job: Job) -> list[Job]:
        """Get all jobs ahead of this job in the queue."""
        if job.status != JobStatus.QUEUED or not job.assigned_worker_id:
            return []
        
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3,
        }
        
        queued_jobs = self.db.query(Job).filter(
            and_(
                Job.status == JobStatus.QUEUED,
                Job.assigned_worker_id == job.assigned_worker_id,
            )
        ).all()
        
        # Sort by priority then created_at
        queued_jobs.sort(
            key=lambda j: (priority_order.get(j.priority, 999), j.created_at)
        )
        
        # Return jobs before this one
        jobs_ahead = []
        for queued_job in queued_jobs:
            if queued_job.id == job.id:
                break
            jobs_ahead.append(queued_job)
        
        return jobs_ahead


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
