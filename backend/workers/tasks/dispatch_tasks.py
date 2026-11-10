from workers.celery_app import celery_app
from infrastructure.database import SessionLocal
from modules.dispatch.application.use_cases import ScheduleReadyTasks, ScheduleTaskExecution
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters


@celery_app.task(name="workers.tasks.dispatch_tasks.schedule_ready_tasks")
def schedule_ready_tasks(limit: int = 20) -> dict:
    with SessionLocal() as db:
        adapters = build_dispatch_adapters(db)
        scheduler = ScheduleTaskExecution(
            adapters.ready_tasks,
            adapters.attempts,
            adapters.offers,
            adapters.automation_versions,
            adapters.candidates,
            adapters.decisions,
            adapters.reservations,
            adapters.locks,
            adapters.commands,
            adapters.outbox,
            adapters.transaction,
        )
        result = ScheduleReadyTasks(adapters.ready_tasks, scheduler, adapters.transaction).execute(limit=limit)
        return {
            "scheduler_run_id": result.scheduler_run_id,
            "scanned": result.scanned,
            "scheduled": result.scheduled,
            "skipped": result.skipped,
        }


@celery_app.task(name="workers.tasks.dispatch_tasks.dispatch_queue")
def dispatch_queue() -> dict:
    """Ciclo da fila (Fase 3): marca jobs perdidos do modo direto e entrega os jobs às máquinas
    livres, na ordem da fila. A oferta ao Agent segue no schedule_ready_tasks."""
    from modules.dispatch.api.fila import despachar_agora

    with SessionLocal() as db:
        resultado = despachar_agora(db)
        return {"perdidos": resultado["perdidos"], "entregues": len(resultado["entregues"])}
