from sqlalchemy.orm import Session

from app.models.worker import Worker
from app.repositories.worker_repository import WorkerRepository


class WorkerService:
    def __init__(self, db: Session) -> None:
        self.workers = WorkerRepository(db)

    def list_workers(self) -> list[Worker]:
        return self.workers.list_all()

    def get_worker(self, worker_id: int) -> Worker:
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError("Worker not found.")
        return worker
