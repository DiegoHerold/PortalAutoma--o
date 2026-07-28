from sqlalchemy.orm import Session

from app.models.job import Job
from app.repositories.automation_repository import AutomationRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas.job import JobRead


class JobEnrichmentService:
    """Compatibility read adapter for the old Jobs API."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
        self.automations = AutomationRepository(db)
        self.workers = WorkerRepository(db)

    def enrich_job(self, job: Job) -> JobRead:
        """Project the legacy Job mirror without legacy queue calculations."""
        automation = self.automations.get(job.automation_id)
        worker = self.workers.get(job.assigned_worker_id) if job.assigned_worker_id else None
        job_dict = {
            "id": job.id,
            "automation_id": job.automation_id,
            "requested_by_user_id": job.requested_by_user_id,
            "status": job.status,
            "priority": job.priority,
            "payload_json": job.payload_json,
            "scheduled_for": job.scheduled_for,
            "assigned_worker_id": job.assigned_worker_id,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "automation_name": automation.name if automation else None,
            "worker_name": worker.name if worker else None,
            "estimated_start": None,
            "estimated_end": None,
            "estimated_duration_seconds": None,
            "queue_position": None,
        }
        
        return JobRead(**job_dict)

    def enrich_jobs(self, jobs: list[Job]) -> list[JobRead]:
        """Enrich multiple jobs with computed fields."""
        return [self.enrich_job(job) for job in jobs]
