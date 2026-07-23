from app.core.constants import JobStatus, WorkerStatus
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.execution import Execution
from app.models.job import Job
from app.models.log import ExecutionLog
from app.models.worker import Worker
from app.services.job_dispatcher_service import JobDispatcherService
from app.services.realtime_service import RealtimeService
from app.utils.datetime import utcnow


@celery_app.task(name="app.tasks.job_tasks.execute_job")
def execute_job(job_id: int) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return {"job_id": job_id, "status": "missing"}

        # Get or create worker
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

        # Update worker and job status
        now = utcnow()
        worker.status = WorkerStatus.BUSY
        worker.last_heartbeat_at = now
        
        # If job isn't already running, set it to running
        if job.status != JobStatus.RUNNING:
            job.status = JobStatus.RUNNING
            job.started_at = now
            job.assigned_worker_id = worker.id

        # Create execution record
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

        # Emit real-time update for job start
        realtime_service = RealtimeService(db)
        realtime_service.emit_job_update(job)

        # Log execution steps
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

        # Complete the job
        finished_at = utcnow()
        execution.execution_status = JobStatus.SUCCESS
        execution.finished_at = finished_at
        execution.result_summary = "Fake execution finished successfully."
        execution.result_payload_json = {
            "job_id": job.id,
            "automation_id": job.automation_id,
            "payload": job.payload_json or {},
            "worker": worker.hostname,
            "status": "success",
        }
        job.status = JobStatus.SUCCESS
        job.finished_at = finished_at
        worker.status = WorkerStatus.ONLINE
        worker.last_heartbeat_at = finished_at

        # Emit real-time update for job completion
        realtime_service.emit_job_update(job)

        db.add(
            ExecutionLog(
                execution_id=execution.id,
                level="INFO",
                message="Job marked as succeeded and persisted.",
            )
        )
        
        db.commit()

        # After job completion, promote next job in queue
        try:
            dispatcher = JobDispatcherService(db)
            next_job = dispatcher.promote_next_job(worker.id)
            if next_job:
                # Emit update for the promoted job
                realtime_service.emit_job_update(next_job)
                # Recalculate ETAs for remaining queued jobs
                realtime_service.recalculate_and_emit_queue_updates(worker.id)
        except Exception as e:
            # Log error but don't fail the main job
            print(f"Error promoting next job: {e}")

        return {"job_id": job_id, "status": "success", "execution_id": execution.id}
