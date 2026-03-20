from sqlalchemy.orm import Session

from app.core.constants import JobStatus
from app.core.celery_app import celery_app
from app.core.permissions import is_admin
from app.models.job import Job
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class JobDispatcherService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.automations = AutomationRepository(db)
        self.jobs = JobRepository(db)
        self.permissions = PermissionService(db)

    def dispatch(self, user: User, payload: JobCreate) -> Job:
        self.permissions.ensure_automation_action(user, payload.automation_id, "can_execute")
        job = Job(
            automation_id=payload.automation_id,
            requested_by_user_id=user.id,
            status=JobStatus.QUEUED,
            priority=payload.priority,
            payload_json=payload.payload_json,
            scheduled_for=payload.scheduled_for,
        )
        job = self.jobs.create(job)
        celery_app.send_task(
            "app.tasks.job_tasks.execute_job",
            kwargs={"job_id": job.id},
            queue=payload.priority,
        )
        self.audit.record(
            "job_dispatched",
            actor_email=user.email,
            resource_type="job",
            resource_id=str(job.id),
            details=f"automation_id={job.automation_id}",
        )
        self.db.commit()
        return job

    def dispatch_system(self, payload: JobCreate) -> Job:
        job = Job(
            automation_id=payload.automation_id,
            requested_by_user_id=None,
            status=JobStatus.QUEUED,
            priority=payload.priority,
            payload_json=payload.payload_json,
            scheduled_for=payload.scheduled_for,
        )
        job = self.jobs.create(job)
        celery_app.send_task(
            "app.tasks.job_tasks.execute_job",
            kwargs={"job_id": job.id},
            queue=payload.priority,
        )
        self.audit.record(
            "job_dispatched",
            actor_email=None,
            resource_type="job",
            resource_id=str(job.id),
            details="system trigger dispatch",
        )
        self.db.commit()
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
