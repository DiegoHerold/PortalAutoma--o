from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from modules.fleet.application.use_cases import DetectStaleAgents
from modules.fleet.infrastructure.adapters import build_fleet_adapters


@celery_app.task(name="app.tasks.housekeeping_tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.tasks.housekeeping_tasks.detect_stale_agents")
def detect_stale_agents() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_fleet_adapters(db)
        return DetectStaleAgents(adapters.agents, adapters.configurations, adapters.transaction).execute()
