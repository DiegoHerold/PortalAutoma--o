from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from modules.dispatch.application.dto import (
    AgentDispatchSnapshotDTO,
    CancellationRequestDTO,
    DispatchDecisionDTO,
    ExecutionLeaseDTO,
    ResourceLockDTO,
    ResourceReservationDTO,
    RetryScheduleDTO,
)
from modules.orchestration.application.dto import AgentSelectionDTO, AgentSelectionRequestDTO, ExecutionOfferDTO, TaskExecutionDTO


class AgentCommandStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransactionManager(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class AgentCommand:
    id: str
    agent_id: str
    agent_instance_id: str | None
    command_sequence: int
    message_type: str
    payload: dict
    status: AgentCommandStatus
    created_at: datetime
    available_at: datetime | None = None
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    expires_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None


class AgentCommandStore(Protocol):
    def append(self, command: AgentCommand) -> None:
        raise NotImplementedError

    def next_pending_for_agent(self, agent_id: str) -> AgentCommand | None:
        raise NotImplementedError


class AgentCommandPort(Protocol):
    def create(self, agent_id: str, message_type: str, payload: dict[str, Any], expires_at: datetime | None = None):
        raise NotImplementedError

    def acknowledge_by_payload(self, agent_id: str, message_type: str, payload_key: str, payload_value: str, status: str, acknowledged_at: datetime):
        raise NotImplementedError


class AgentSelectionPort(Protocol):
    def select(self, request: AgentSelectionRequestDTO) -> AgentSelectionDTO:
        raise NotImplementedError


class ExecutionOfferRepository(Protocol):
    def add(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        raise NotImplementedError

    def save(self, offer: ExecutionOfferDTO, commit_token_hash: str | None = None) -> ExecutionOfferDTO:
        raise NotImplementedError

    def get(self, offer_id: str) -> ExecutionOfferDTO | None:
        raise NotImplementedError

    def current_for_attempt(self, execution_attempt_id: str) -> ExecutionOfferDTO | None:
        raise NotImplementedError

    def current_for_execution(self, execution_id: str) -> ExecutionOfferDTO | None:
        raise NotImplementedError

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ExecutionOfferDTO]:
        raise NotImplementedError

    def list_for_attempt(self, execution_attempt_id: str) -> list[ExecutionOfferDTO]:
        raise NotImplementedError


class ReadyTaskRepository(Protocol):
    def claim_ready(self, now: datetime, limit: int) -> list[TaskExecutionDTO]:
        raise NotImplementedError

    def get(self, task_execution_id: str) -> TaskExecutionDTO | None:
        raise NotImplementedError

    def save(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        raise NotImplementedError


class DispatchCandidateReader(Protocol):
    def list_candidates(self, preferred_agent_id: str | None = None) -> list[AgentDispatchSnapshotDTO]:
        raise NotImplementedError

    def active_attempt_count(self, agent_id: str) -> int:
        raise NotImplementedError


class DispatchDecisionRepository(Protocol):
    def add(self, decision: DispatchDecisionDTO) -> DispatchDecisionDTO:
        raise NotImplementedError

    def get(self, decision_id: str) -> DispatchDecisionDTO | None:
        raise NotImplementedError

    def list_for_task(self, task_execution_id: str) -> list[DispatchDecisionDTO]:
        raise NotImplementedError

    def list_for_execution(self, execution_id: str) -> list[DispatchDecisionDTO]:
        raise NotImplementedError


class OfferReservationPort(Protocol):
    def reserve(self, reservation: ResourceReservationDTO) -> ResourceReservationDTO:
        raise NotImplementedError

    def release_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError

    def convert_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError

    def release_for_attempt(self, execution_attempt_id: str, now: datetime, reason: str) -> None:
        raise NotImplementedError

    def list_for_attempt(self, execution_attempt_id: str) -> list[ResourceReservationDTO]:
        raise NotImplementedError

    def active_units(self, agent_id: str, pool_type: str) -> int:
        raise NotImplementedError


class ResourceLockRepository(Protocol):
    def add(self, lock: ResourceLockDTO) -> ResourceLockDTO:
        raise NotImplementedError

    def save(self, lock: ResourceLockDTO) -> ResourceLockDTO:
        raise NotImplementedError

    def active_conflict(self, normalized_key: str, scope: str) -> ResourceLockDTO | None:
        raise NotImplementedError

    def list_for_attempt(self, execution_attempt_id: str) -> list[ResourceLockDTO]:
        raise NotImplementedError

    def release_for_attempt(self, execution_attempt_id: str, now: datetime, reason: str) -> None:
        raise NotImplementedError

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ResourceLockDTO]:
        raise NotImplementedError


class ExecutionLeaseRepository(Protocol):
    def add(self, lease: ExecutionLeaseDTO) -> ExecutionLeaseDTO:
        raise NotImplementedError

    def save(self, lease: ExecutionLeaseDTO) -> ExecutionLeaseDTO:
        raise NotImplementedError

    def get(self, lease_id: str) -> ExecutionLeaseDTO | None:
        raise NotImplementedError

    def active_for_attempt(self, execution_attempt_id: str) -> ExecutionLeaseDTO | None:
        raise NotImplementedError

    def due_for_suspect(self, now: datetime, limit: int = 100) -> list[ExecutionLeaseDTO]:
        raise NotImplementedError

    def due_for_expiration(self, now: datetime, limit: int = 100) -> list[ExecutionLeaseDTO]:
        raise NotImplementedError


class RetryScheduleRepository(Protocol):
    def add(self, schedule: RetryScheduleDTO) -> RetryScheduleDTO:
        raise NotImplementedError

    def save(self, schedule: RetryScheduleDTO) -> RetryScheduleDTO:
        raise NotImplementedError

    def due(self, now: datetime, limit: int = 100) -> list[RetryScheduleDTO]:
        raise NotImplementedError


class CancellationRequestRepository(Protocol):
    def add(self, request: CancellationRequestDTO) -> CancellationRequestDTO:
        raise NotImplementedError

    def save(self, request: CancellationRequestDTO) -> CancellationRequestDTO:
        raise NotImplementedError

    def current_for_execution(self, execution_id: str) -> CancellationRequestDTO | None:
        raise NotImplementedError

    def due_for_force(self, now: datetime, limit: int = 100) -> list[CancellationRequestDTO]:
        raise NotImplementedError


class ReconciliationRecordRepository(Protocol):
    def add(self, record) -> Any:
        raise NotImplementedError


class OutboxPort(Protocol):
    def append_event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any], correlation_id: str | None = None, causation_id: str | None = None) -> None:
        raise NotImplementedError


DispatchOutbox = OutboxPort
