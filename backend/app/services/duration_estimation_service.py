from datetime import datetime, timedelta
import statistics
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.config import get_settings
from app.core.constants import JobStatus
from app.models.job import Job
from app.repositories.automation_repository import AutomationRepository
from app.repositories.job_repository import JobRepository


class DurationEstimationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.jobs = JobRepository(db)
        self.automations = AutomationRepository(db)

    def estimate_duration(self, automation_id: int, worker_id: int | None = None) -> int:
        """
        Estimate job duration in seconds using percentile calculation.
        Returns the configured percentile (default p75) of historical durations.
        
        Fallback strategy:
        1. Try automation + worker pair history
        2. Try automation history (any worker)
        3. Use automation.timeout_seconds
        """
        window = self.settings.eta_window
        percentile = self.settings.eta_percentile
        
        # Try automation + worker pair
        if worker_id:
            durations = self._get_historical_durations(automation_id, worker_id, window)
            if len(durations) >= 3:  # Minimum samples for percentile
                return int(statistics.quantiles(durations, n=100)[percentile - 1])
        
        # Fallback: try automation history (any worker)
        durations = self._get_historical_durations(automation_id, None, window)
        if len(durations) >= 3:
            return int(statistics.quantiles(durations, n=100)[percentile - 1])
        
        # Fallback: use automation timeout
        automation = self.automations.get(automation_id)
        return automation.timeout_seconds if automation else 300

    def _get_historical_durations(
        self, automation_id: int, worker_id: int | None, limit: int
    ) -> list[float]:
        """Get historical job durations in seconds."""
        query = self.db.query(Job).filter(
            and_(
                Job.automation_id == automation_id,
                Job.status == JobStatus.SUCCESS,
                Job.started_at.isnot(None),
                Job.finished_at.isnot(None),
            )
        )
        
        if worker_id:
            query = query.filter(Job.assigned_worker_id == worker_id)
        
        jobs = query.order_by(Job.finished_at.desc()).limit(limit).all()
        
        durations = []
        for job in jobs:
            if job.started_at and job.finished_at:
                duration = (job.finished_at - job.started_at).total_seconds()
                if duration > 0:
                    durations.append(duration)
        
        return durations

    def compute_job_eta(
        self, 
        job: Job, 
        queue_position: int | None = None,
        jobs_ahead: list[Job] | None = None
    ) -> tuple[datetime | None, datetime | None, int | None]:
        """
        Compute estimated start, end times and duration for a job.
        
        Returns: (estimated_start, estimated_end, estimated_duration_seconds)
        """
        estimated_duration = self.estimate_duration(job.automation_id, job.assigned_worker_id)
        
        if job.status == JobStatus.RUNNING:
            if job.started_at:
                estimated_end = job.started_at + timedelta(seconds=estimated_duration)
                return None, estimated_end, estimated_duration
            return None, None, estimated_duration
        
        elif job.status == JobStatus.QUEUED:
            now = datetime.now(job.created_at.tzinfo if job.created_at else None)
            estimated_start = now
            
            # Add estimated durations of all jobs ahead in queue
            if jobs_ahead:
                for job_ahead in jobs_ahead:
                    duration_ahead = self.estimate_duration(
                        job_ahead.automation_id, 
                        job_ahead.assigned_worker_id
                    )
                    estimated_start += timedelta(seconds=duration_ahead)
            
            estimated_end = estimated_start + timedelta(seconds=estimated_duration)
            return estimated_start, estimated_end, estimated_duration
        
        return None, None, None
