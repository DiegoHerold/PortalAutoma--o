from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Job]:
        return list(self.db.scalars(select(Job).order_by(Job.created_at.desc())).all())

    def get(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def create(self, job: Job) -> Job:
        self.db.add(job)
        self.db.flush()  # Use flush instead of commit for transactions
        return job
