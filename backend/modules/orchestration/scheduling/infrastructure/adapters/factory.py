from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.orchestration.infrastructure.repositories import SqlAlchemyOrchestrationOutbox, SqlAlchemyOrchestrationTransaction
from modules.orchestration.scheduling.infrastructure.adapters.execution_creator import ModuleScheduleExecutionCreator
from modules.orchestration.scheduling.infrastructure.repositories import SqlAlchemyScheduleExecutionRepository, SqlAlchemyScheduleRepository


@dataclass(frozen=True)
class ScheduleAdapters:
    schedules: SqlAlchemyScheduleRepository
    executions: SqlAlchemyScheduleExecutionRepository
    creator: ModuleScheduleExecutionCreator
    outbox: SqlAlchemyOrchestrationOutbox
    audit: SqlAlchemyAuditEventRepository
    transaction: SqlAlchemyOrchestrationTransaction


def build_schedule_adapters(db: Session) -> ScheduleAdapters:
    return ScheduleAdapters(
        schedules=SqlAlchemyScheduleRepository(db),
        executions=SqlAlchemyScheduleExecutionRepository(db),
        creator=ModuleScheduleExecutionCreator(db),
        outbox=SqlAlchemyOrchestrationOutbox(db),
        audit=SqlAlchemyAuditEventRepository(db),
        transaction=SqlAlchemyOrchestrationTransaction(db),
    )
