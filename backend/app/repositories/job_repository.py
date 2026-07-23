from sqlalchemy import select, and_
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

    def get_queued_by_worker(self, worker_id: int) -> list[Job]:
        """Get all queued jobs assigned to a specific worker."""
        return list(
            self.db.scalars(
                select(Job)
                .where(and_(Job.status == "queued", Job.assigned_worker_id == worker_id))
                .order_by(Job.created_at)
            ).all()
        )

    def get_all_queued(self) -> list[Job]:
        """Get all queued jobs."""
        return list(
            self.db.scalars(
                select(Job)
                .where(Job.status == "queued")
                .order_by(Job.created_at)
            ).all()
        )

    def get_running_by_worker(self, worker_id: int) -> list[Job]:
        """Get all running jobs for a specific worker."""
        return list(
            self.db.scalars(
                select(Job)
                .where(and_(Job.status == "running", Job.assigned_worker_id == worker_id))
            ).all()
        )

    def count_running_by_worker(self, worker_id: int) -> int:
        """Count running jobs for a specific worker."""
        return len(self.get_running_by_worker(worker_id))
