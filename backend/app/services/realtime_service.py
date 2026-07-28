import json
from typing import Dict, Any

import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job
from app.repositories.automation_repository import AutomationRepository
from app.repositories.worker_repository import WorkerRepository


class RealtimeService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.redis_client = redis.from_url(self.settings.redis_url)
        self.automations = AutomationRepository(db)
        self.workers = WorkerRepository(db)

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
        """Serialize the legacy Job mirror without legacy queue calculations."""
        automation = self.automations.get(job.automation_id)
        worker = self.workers.get(job.assigned_worker_id) if job.assigned_worker_id else None
        
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
            "estimated_start": None,
            "estimated_end": None,
            "estimated_duration_seconds": None,
            "queue_position": None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

    def recalculate_and_emit_queue_updates(self, worker_id: int | None = None) -> None:
        """Legacy hook kept for compatibility; Scheduler state now lives in Dispatch."""
        return None
