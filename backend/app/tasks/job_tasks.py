from app.core.constants import JobStatus, WorkerStatus
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.execution import Execution
from app.models.job import Job
from app.models.log import ExecutionLog
from app.models.worker import Worker
from app.utils.datetime import utcnow


@celery_app.task(name="app.tasks.job_tasks.execute_job")
def execute_job(job_id: int) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return {"job_id": job_id, "status": "missing"}

        worker = db.query(Worker).filter(Worker.hostname == "local-simulated-worker").first()
        if worker is None:
            worker = Worker(
                name="Local Simulated Worker",
                hostname="local-simulated-worker",
                ip_address="127.0.0.1",
                status=WorkerStatus.ONLINE,
                max_concurrency=1,
                is_active=True,
            )
            db.add(worker)
            db.flush()

        now = utcnow()
        worker.status = WorkerStatus.BUSY
        worker.last_heartbeat_at = now
        job.status = JobStatus.RUNNING
        job.started_at = now
        job.assigned_worker_id = worker.id

        execution = Execution(
            job_id=job.id,
            worker_id=worker.id,
            execution_status=JobStatus.RUNNING,
            started_at=now,
            result_summary="Fake execution started.",
            result_payload_json={"step": "started"},
        )
        db.add(execution)
        db.flush()

        db.add(
            ExecutionLog(
                execution_id=execution.id,
                level="INFO",
                message="Job accepted by simulated worker.",
            )
        )
        db.add(
            ExecutionLog(
                execution_id=execution.id,
                level="INFO",
                message="Fake executor processed the payload successfully.",
            )
        )

        finished_at = utcnow()
        execution.execution_status = JobStatus.SUCCEEDED
        execution.finished_at = finished_at
        execution.result_summary = "Fake execution finished successfully."
        execution.result_payload_json = {
            "job_id": job.id,
            "automation_id": job.automation_id,
            "payload": job.payload_json or {},
            "worker": worker.hostname,
            "status": "succeeded",
        }
        job.status = JobStatus.SUCCEEDED
        job.finished_at = finished_at
        worker.status = WorkerStatus.ONLINE
        worker.last_heartbeat_at = finished_at

        db.add(
            ExecutionLog(
                execution_id=execution.id,
                level="INFO",
                message="Job marked as succeeded and persisted.",
            )
        )
        db.commit()

        return {"job_id": job_id, "status": "succeeded", "execution_id": execution.id}
