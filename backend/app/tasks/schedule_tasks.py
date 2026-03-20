from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.schedule_tasks.sync")
def sync_schedules() -> str:
    return "ok"
