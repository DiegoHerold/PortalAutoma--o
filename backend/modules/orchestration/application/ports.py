from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from modules.orchestration.application.dto import (
    AgentSelectionDTO,
    AgentSelectionRequestDTO,
    AutomationVersionSnapshotDTO,
    ExecutionAttemptDTO,
    ExecutionDTO,
    ExecutionDetailsDTO,
    ExecutionOfferDTO,
    ResourceReservationDTO,
    TaskExecutionDTO,
)


class TransactionManager(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class ExecutionRepository(Protocol):
    def add(self, execution: ExecutionDTO) -> ExecutionDTO:
        raise NotImplementedError

    def save(self, execution: ExecutionDTO) -> ExecutionDTO:
        raise NotImplementedError

    def get(self, execution_id: str) -> ExecutionDTO | None:
        raise NotImplementedError

    def list(self, limit: int = 100, offset: int = 0) -> list[ExecutionDTO]:
        raise NotImplementedError


class TaskExecutionRepository(Protocol):
    def add(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        raise NotImplementedError

    def save(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        raise NotImplementedError

    def get(self, task_execution_id: str) -> TaskExecutionDTO | None:
        raise NotImplementedError

    def list_for_execution(self, execution_id: str) -> list[TaskExecutionDTO]:
        raise NotImplementedError


class ExecutionAttemptRepository(Protocol):
    def add(self, attempt: ExecutionAttemptDTO) -> ExecutionAttemptDTO:
        raise NotImplementedError

    def save(self, attempt: ExecutionAttemptDTO) -> ExecutionAttemptDTO:
        raise NotImplementedError

    def get(self, execution_attempt_id: str) -> ExecutionAttemptDTO | None:
        raise NotImplementedError

    def next_attempt_number(self, task_execution_id: str) -> int:
        raise NotImplementedError

    def list_for_execution(self, execution_id: str) -> list[ExecutionAttemptDTO]:
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


class OfferReservationPort(Protocol):
    def reserve(self, reservation: ResourceReservationDTO) -> ResourceReservationDTO:
        raise NotImplementedError

    def release_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError

    def convert_for_offer(self, offer_id: str, now: datetime) -> None:
        raise NotImplementedError

    def list_for_offer(self, offer_id: str) -> list[ResourceReservationDTO]:
        raise NotImplementedError


class AutomationVersionReader(Protocol):
    def get_published_snapshot(self, automation_version_id: int) -> AutomationVersionSnapshotDTO | None:
        raise NotImplementedError


class AgentSelectionPort(Protocol):
    def select(self, request: AgentSelectionRequestDTO) -> AgentSelectionDTO:
        raise NotImplementedError

    def get_agent_summary(self, agent_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class AgentCommandPort(Protocol):
    def create(self, agent_id: str, message_type: str, payload: dict[str, Any], expires_at: datetime | None = None):
        raise NotImplementedError


class OutboxPort(Protocol):
    def append_event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any], correlation_id: str | None = None, causation_id: str | None = None) -> None:
        raise NotImplementedError


class Clock(Protocol):
    def now(self) -> datetime:
        raise NotImplementedError


class IdGenerator(Protocol):
    def new_id(self, prefix: str) -> str:
        raise NotImplementedError
