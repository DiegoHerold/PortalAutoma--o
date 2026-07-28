from __future__ import annotations

from workers.celery_app import celery_app
from infrastructure.database import SessionLocal
from modules.orchestration.flows.infrastructure.adapters import build_flow_adapters
from modules.orchestration.infrastructure.repositories import SqlAlchemyExecutionRepository
from modules.orchestration.scheduling.application import ReconcileScheduleExecutions, TriggerDueSchedules
from modules.orchestration.scheduling.infrastructure.adapters import build_schedule_adapters


@celery_app.task(name="workers.tasks.schedule_tasks.sync")
def sync_schedules() -> str:
    with SessionLocal() as db:
        adapters = build_schedule_adapters(db)
        trigger_result = TriggerDueSchedules(
            adapters.schedules,
            adapters.executions,
            adapters.creator,
            adapters.outbox,
            adapters.transaction,
        ).execute()
        flow_adapters = build_flow_adapters(db)
        reconcile_result = ReconcileScheduleExecutions(
            adapters.executions,
            SqlAlchemyExecutionRepository(db),
            flow_adapters.flow_executions,
            adapters.outbox,
            adapters.transaction,
        ).execute()
    return (
        f"triggered={trigger_result['triggered']} "
        f"skipped={trigger_result['skipped']} "
        f"failed={trigger_result['failed']} "
        f"errors={trigger_result['errors']} "
        f"reconciled={reconcile_result['reconciled']}"
    )
