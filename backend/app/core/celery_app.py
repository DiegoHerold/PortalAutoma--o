from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "portal_automacoes",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_default_queue = "normal"
celery_app.conf.task_routes = {
    "app.tasks.job_tasks.execute_job": {"queue": "normal"},
}
