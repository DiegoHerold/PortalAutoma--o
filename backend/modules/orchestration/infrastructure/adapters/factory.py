from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.dispatch.infrastructure.repositories.sqlalchemy_dispatch import (
    SimpleAgentSelectionAdapter,
    SqlAlchemyAutomationVersionReader,
    SqlAlchemyExecutionOfferRepository,
    SqlAlchemyOfferReservationRepository,
)
from modules.fleet.infrastructure.repositories import SqlAlchemyAgentCommandRepository
from modules.governance.infrastructure.repositories import SqlAlchemyAuditEventRepository
from modules.orchestration.infrastructure.repositories import (
    SqlAlchemyExecutionAttemptRepository,
    SqlAlchemyExecutionRepository,
    SqlAlchemyOrchestrationOutbox,
    SqlAlchemyOrchestrationTransaction,
    SqlAlchemyTaskExecutionRepository,
)
from modules.shared.infrastructure.repositories.sqlalchemy_idempotency import SqlAlchemyIdempotencyStore


@dataclass(frozen=True)
class OrchestrationAdapters:
    executions: SqlAlchemyExecutionRepository
    tasks: SqlAlchemyTaskExecutionRepository
    attempts: SqlAlchemyExecutionAttemptRepository
    offers: SqlAlchemyExecutionOfferRepository
    reservations: SqlAlchemyOfferReservationRepository
    automation_versions: SqlAlchemyAutomationVersionReader
    agent_selection: SimpleAgentSelectionAdapter
    commands: SqlAlchemyAgentCommandRepository
    outbox: SqlAlchemyOrchestrationOutbox
    audit: SqlAlchemyAuditEventRepository
    idempotency: SqlAlchemyIdempotencyStore
    transaction: SqlAlchemyOrchestrationTransaction


def build_orchestration_adapters(db: Session) -> OrchestrationAdapters:
    return OrchestrationAdapters(
        executions=SqlAlchemyExecutionRepository(db),
        tasks=SqlAlchemyTaskExecutionRepository(db),
        attempts=SqlAlchemyExecutionAttemptRepository(db),
        offers=SqlAlchemyExecutionOfferRepository(db),
        reservations=SqlAlchemyOfferReservationRepository(db),
        automation_versions=SqlAlchemyAutomationVersionReader(db),
        agent_selection=SimpleAgentSelectionAdapter(db),
        commands=SqlAlchemyAgentCommandRepository(db),
        outbox=SqlAlchemyOrchestrationOutbox(db),
        audit=SqlAlchemyAuditEventRepository(db),
        idempotency=SqlAlchemyIdempotencyStore(db),
        transaction=SqlAlchemyOrchestrationTransaction(db),
    )
