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
