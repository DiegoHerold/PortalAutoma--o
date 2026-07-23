from sqlalchemy.orm import Session

from app.models.worker import Worker
from app.repositories.worker_repository import WorkerRepository
from app.repositories.job_repository import JobRepository
from app.schemas.worker import WorkerRead


class WorkerService:
    def __init__(self, db: Session) -> None:
        self.workers = WorkerRepository(db)
        self.jobs = JobRepository(db)

    def list_workers(self) -> list[WorkerRead]:
        """List all workers with active job counts."""
        workers = self.workers.list_all()
        worker_data = []
        
        for worker in workers:
            active_jobs = self.jobs.count_running_by_worker(worker.id)
            worker_dict = {
                "id": worker.id,
                "name": worker.name,
                "hostname": worker.hostname,
                "ip_address": worker.ip_address,
                "status": worker.status,
                "max_concurrency": worker.max_concurrency,
                "last_heartbeat_at": worker.last_heartbeat_at,
                "is_active": worker.is_active,
                "active_jobs": active_jobs,
            }
            worker_data.append(WorkerRead(**worker_dict))
        
        return worker_data

    def get_worker(self, worker_id: int) -> WorkerRead:
        """Get a worker with active job count."""
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        
        active_jobs = self.jobs.count_running_by_worker(worker.id)
        worker_dict = {
            "id": worker.id,
            "name": worker.name,
            "hostname": worker.hostname,
            "ip_address": worker.ip_address,
            "status": worker.status,
            "max_concurrency": worker.max_concurrency,
            "last_heartbeat_at": worker.last_heartbeat_at,
            "is_active": worker.is_active,
            "active_jobs": active_jobs,
        }
        
        return WorkerRead(**worker_dict)

    def get_worker_model(self, worker_id: int) -> Worker:
        """Get the raw worker model."""
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        return worker
