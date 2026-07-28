from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.dispatch.infrastructure.repositories import (
    SqlAlchemyAutomationVersionReader,
    SqlAlchemyCancellationRequestRepository,
    SqlAlchemyDispatchCandidateReader,
    SqlAlchemyDispatchDecisionRepository,
    SqlAlchemyExecutionLeaseRepository,
    SqlAlchemyExecutionOfferRepository,
    SqlAlchemyOfferReservationRepository,
    SqlAlchemyReadyTaskRepository,
    SqlAlchemyReconciliationRecordRepository,
    SqlAlchemyResourceLockRepository,
    SqlAlchemyRetryScheduleRepository,
)
from modules.fleet.infrastructure.repositories import SqlAlchemyAgentCommandRepository
from modules.orchestration.infrastructure.repositories import (
    SqlAlchemyExecutionAttemptRepository,
    SqlAlchemyExecutionRepository,
    SqlAlchemyOrchestrationOutbox,
    SqlAlchemyOrchestrationTransaction,
    SqlAlchemyTaskExecutionRepository,
)


@dataclass(frozen=True)
class DispatchAdapters:
    executions: SqlAlchemyExecutionRepository
    tasks: SqlAlchemyTaskExecutionRepository
    ready_tasks: SqlAlchemyReadyTaskRepository
    attempts: SqlAlchemyExecutionAttemptRepository
    offers: SqlAlchemyExecutionOfferRepository
    reservations: SqlAlchemyOfferReservationRepository
    locks: SqlAlchemyResourceLockRepository
    leases: SqlAlchemyExecutionLeaseRepository
    retry_schedules: SqlAlchemyRetryScheduleRepository
    cancellation_requests: SqlAlchemyCancellationRequestRepository
    reconciliations: SqlAlchemyReconciliationRecordRepository
    decisions: SqlAlchemyDispatchDecisionRepository
    candidates: SqlAlchemyDispatchCandidateReader
    automation_versions: SqlAlchemyAutomationVersionReader
    commands: SqlAlchemyAgentCommandRepository
    outbox: SqlAlchemyOrchestrationOutbox
    transaction: SqlAlchemyOrchestrationTransaction


def build_dispatch_adapters(db: Session) -> DispatchAdapters:
    return DispatchAdapters(
        executions=SqlAlchemyExecutionRepository(db),
        tasks=SqlAlchemyTaskExecutionRepository(db),
        ready_tasks=SqlAlchemyReadyTaskRepository(db),
        attempts=SqlAlchemyExecutionAttemptRepository(db),
        offers=SqlAlchemyExecutionOfferRepository(db),
        reservations=SqlAlchemyOfferReservationRepository(db),
        locks=SqlAlchemyResourceLockRepository(db),
        leases=SqlAlchemyExecutionLeaseRepository(db),
        retry_schedules=SqlAlchemyRetryScheduleRepository(db),
        cancellation_requests=SqlAlchemyCancellationRequestRepository(db),
        reconciliations=SqlAlchemyReconciliationRecordRepository(db),
        decisions=SqlAlchemyDispatchDecisionRepository(db),
        candidates=SqlAlchemyDispatchCandidateReader(db),
        automation_versions=SqlAlchemyAutomationVersionReader(db),
        commands=SqlAlchemyAgentCommandRepository(db),
        outbox=SqlAlchemyOrchestrationOutbox(db),
        transaction=SqlAlchemyOrchestrationTransaction(db),
    )


__all__ = ["DispatchAdapters", "build_dispatch_adapters"]
