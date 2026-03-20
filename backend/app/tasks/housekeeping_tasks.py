from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.housekeeping_tasks.ping")
def ping() -> str:
    return "pong"
