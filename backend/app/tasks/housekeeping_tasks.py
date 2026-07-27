from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from modules.fleet.application.use_cases import DetectStaleAgents
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.orchestration.application.use_cases import ExpireExecutionOffer
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters


@celery_app.task(name="app.tasks.housekeeping_tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.tasks.housekeeping_tasks.detect_stale_agents")
def detect_stale_agents() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_fleet_adapters(db)
        return DetectStaleAgents(adapters.agents, adapters.configurations, adapters.transaction).execute()


@celery_app.task(name="app.tasks.housekeeping_tasks.expire_execution_offers")
def expire_execution_offers() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_orchestration_adapters(db)
        return ExpireExecutionOffer(
            adapters.attempts,
            adapters.offers,
            adapters.reservations,
            adapters.outbox,
            adapters.transaction,
        ).execute_due()
