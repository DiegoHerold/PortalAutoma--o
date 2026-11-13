from workers.celery_app import celery_app
from infrastructure.database import SessionLocal
from modules.fleet.application.use_cases import DetectStaleAgents
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.dispatch.application.use_cases import ExpireExecutionOffer, ReconcileExpiredLeases
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.orchestration.application.use_cases import DetectLostAttempts, ForceCancelExecutionAttempt


@celery_app.task(name="workers.tasks.housekeeping_tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="workers.tasks.housekeeping_tasks.detect_stale_agents")
def detect_stale_agents() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_fleet_adapters(db)
        return DetectStaleAgents(adapters.agents, adapters.configurations, adapters.transaction).execute()


@celery_app.task(name="workers.tasks.housekeeping_tasks.expire_execution_offers")
def expire_execution_offers() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_dispatch_adapters(db)
        return ExpireExecutionOffer(
            adapters.attempts,
            adapters.tasks,
            adapters.offers,
            adapters.reservations,
            adapters.locks,
            adapters.outbox,
            adapters.transaction,
        ).execute_due()


@celery_app.task(name="workers.tasks.housekeeping_tasks.reconcile_expired_leases")
def reconcile_expired_leases() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_dispatch_adapters(db)
        return ReconcileExpiredLeases(adapters.leases, adapters.outbox, adapters.transaction).execute()


@celery_app.task(name="workers.tasks.housekeeping_tasks.detect_lost_attempts")
def detect_lost_attempts() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_dispatch_adapters(db)
        return DetectLostAttempts(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.leases,
            adapters.retry_schedules,
            adapters.reservations,
            adapters.locks,
            adapters.outbox,
            adapters.transaction,
        ).execute()


@celery_app.task(name="workers.tasks.housekeeping_tasks.force_cancel_execution_attempts")
def force_cancel_execution_attempts() -> dict[str, int]:
    with SessionLocal() as db:
        adapters = build_dispatch_adapters(db)
        return ForceCancelExecutionAttempt(
            adapters.executions,
            adapters.tasks,
            adapters.attempts,
            adapters.cancellation_requests,
            adapters.reservations,
            adapters.locks,
            adapters.leases,
            adapters.outbox,
            adapters.transaction,
        ).execute_due()


@celery_app.task(name="workers.tasks.housekeeping_tasks.aplicar_limpeza_do_sistema")
def aplicar_limpeza_do_sistema() -> dict[str, int]:
    """Regras de limpeza do sistema (Governança > Retenção). Cada passada apaga um lote por regra."""
    from modules.governance.infrastructure.adapters.limpeza import build_aplicar_limpeza

    with SessionLocal() as db:
        return build_aplicar_limpeza(db).execute()
