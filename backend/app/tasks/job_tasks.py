from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.job_tasks.execute_job")
def execute_job(job_id: int) -> dict:
    return {
        "job_id": job_id,
        "status": "delegated_to_dispatch",
        "message": "Legacy Celery execution is disabled; executions are scheduled through backend/modules/dispatch and Agent Gateway.",
    }
