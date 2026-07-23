import json
import redis
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.config import get_settings
from app.models.job import Job
from app.services.duration_estimation_service import DurationEstimationService
from app.repositories.automation_repository import AutomationRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.job_dispatcher_service import JobDispatcherService


class RealtimeService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.redis_client = redis.from_url(self.settings.redis_url)
        self.duration_service = DurationEstimationService(db)
        self.automations = AutomationRepository(db)
        self.workers = WorkerRepository(db)
        self.dispatcher = JobDispatcherService(db)

    def emit_job_update(self, job: Job) -> None:
        """Emit a job update event via Redis pub/sub and WebSocket."""
        job_data = self._serialize_job_for_ws(job)
        
        # Publish to Redis for multi-instance support
        self.redis_client.publish(
            "job_updates",
            json.dumps({
                "type": "job_update",
                "data": job_data
            })
        )

    def _serialize_job_for_ws(self, job: Job) -> Dict[str, Any]:
        """Serialize job for WebSocket transmission."""
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
        
        return {
            "id": job.id,
            "automation_id": job.automation_id,
            "automation_name": automation.name if automation else None,
            "status": job.status,
            "priority": job.priority,
            "assigned_worker_id": job.assigned_worker_id,
            "worker_name": worker.name if worker else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "estimated_start": estimated_start.isoformat() if estimated_start else None,
            "estimated_end": estimated_end.isoformat() if estimated_end else None,
            "estimated_duration_seconds": estimated_duration,
            "queue_position": queue_position,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

    def recalculate_and_emit_queue_updates(self, worker_id: int | None = None) -> None:
        """
        Recalculate ETAs for queued jobs and emit updates.
        Called when queue changes (job starts, finishes, or is added).
        """
        if worker_id:
            # Recalculate for specific worker's queue
            from app.repositories.job_repository import JobRepository
            job_repo = JobRepository(self.db)
            queued_jobs = job_repo.get_queued_by_worker(worker_id)
        else:
            # Recalculate all queued jobs
            from app.repositories.job_repository import JobRepository  
            job_repo = JobRepository(self.db)
            queued_jobs = job_repo.get_all_queued()
        
        for job in queued_jobs:
            self.emit_job_update(job)