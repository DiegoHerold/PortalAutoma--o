from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.worker import Worker


class WorkerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Worker]:
        return list(self.db.scalars(select(Worker).order_by(Worker.name)).all())

    def get(self, worker_id: int) -> Worker | None:
        return self.db.get(Worker, worker_id)

    def create(self, worker: Worker) -> Worker:
        self.db.add(worker)
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def update(self, worker: Worker) -> Worker:
        self.db.add(worker)
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def delete(self, worker: Worker) -> None:
        self.db.delete(worker)
        self.db.commit()
