from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobRead
from app.services.duration_estimation_service import DurationEstimationService
from app.services.job_dispatcher_service import JobDispatcherService
from app.repositories.automation_repository import AutomationRepository
from app.repositories.worker_repository import WorkerRepository


class JobEnrichmentService:
    """Service to enrich jobs with additional computed fields."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
        self.duration_service = DurationEstimationService(db)
        self.dispatcher = JobDispatcherService(db)
        self.automations = AutomationRepository(db)
        self.workers = WorkerRepository(db)

    def enrich_job(self, job: Job) -> JobRead:
        """Enrich a single job with computed fields."""
        # Get related entities
        automation = self.automations.get(job.automation_id)
        worker = self.workers.get(job.assigned_worker_id) if job.assigned_worker_id else None
        
        # Calculate ETA and queue position
        queue_position = None
        estimated_start = None
        estimated_end = None
        estimated_duration = None
        
        if job.status == "queued":
            queue_position = self.dispatcher.get_queue_position(job)
            jobs_ahead = self.dispatcher.get_jobs_ahead(job)
            estimated_start, estimated_end, estimated_duration = self.duration_service.compute_job_eta(
                job, queue_position, jobs_ahead
            )
        elif job.status == "running":
            _, estimated_end, estimated_duration = self.duration_service.compute_job_eta(job)
        
        # Build enriched job data
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
            "estimated_start": estimated_start,
            "estimated_end": estimated_end,
            "estimated_duration_seconds": estimated_duration,
            "queue_position": queue_position,
        }
        
        return JobRead(**job_dict)

    def enrich_jobs(self, jobs: list[Job]) -> list[JobRead]:
        """Enrich multiple jobs with computed fields."""
        return [self.enrich_job(job) for job in jobs]