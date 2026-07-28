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
    "app.tasks.dispatch_tasks.schedule_ready_tasks": {"queue": "normal"},
    "app.tasks.flow_tasks.sync_flow_nodes": {"queue": "normal"},
    "app.tasks.schedule_tasks.sync": {"queue": "normal"},
}

# Import so Celery Beat (and the worker's task registry) knows about it --
# Beat only schedules tasks that have already been imported/registered.
from app.tasks import schedule_tasks  # noqa: E402,F401
from app.tasks import flow_tasks  # noqa: E402,F401
from app.tasks import housekeeping_tasks  # noqa: E402,F401
from app.tasks import dispatch_tasks  # noqa: E402,F401

celery_app.conf.beat_schedule = {
    "sync-schedules-every-minute": {
        "task": "app.tasks.schedule_tasks.sync",
        "schedule": 60.0,
    },
    "detect-stale-agents-every-minute": {
        "task": "app.tasks.housekeeping_tasks.detect_stale_agents",
        "schedule": 60.0,
    },
    "expire-execution-offers-every-30-seconds": {
        "task": "app.tasks.housekeeping_tasks.expire_execution_offers",
        "schedule": 30.0,
    },
    "schedule-ready-tasks-every-5-seconds": {
        "task": "app.tasks.dispatch_tasks.schedule_ready_tasks",
        "schedule": 5.0,
    },
    "sync-flow-nodes-every-5-seconds": {
        "task": "app.tasks.flow_tasks.sync_flow_nodes",
        "schedule": 5.0,
    },
    "reconcile-expired-leases-every-15-seconds": {
        "task": "app.tasks.housekeeping_tasks.reconcile_expired_leases",
        "schedule": 15.0,
    },
    "detect-lost-attempts-every-20-seconds": {
        "task": "app.tasks.housekeeping_tasks.detect_lost_attempts",
        "schedule": 20.0,
    },
    "force-cancel-executions-every-30-seconds": {
        "task": "app.tasks.housekeeping_tasks.force_cancel_execution_attempts",
        "schedule": 30.0,
    },
}
celery_app.conf.timezone = "UTC"
