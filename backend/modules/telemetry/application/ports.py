from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from modules.telemetry.application.dto import (
    AttemptTelemetryContextDTO,
    EventAcknowledgementDTO,
    ExecutionEventDTO,
    ExecutionMetricDTO,
    ExecutionProcessDTO,
    ExecutionProgressDTO,
    TelemetrySummaryDTO,
)


class InboxMessageStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    message_type: str
    received_at: datetime
    status: InboxMessageStatus
    payload: dict


class InboxStore(Protocol):
    def record_once(self, message: InboxMessage) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    message_type: str
    payload: dict
    created_at: datetime


class TransactionalOutbox(Protocol):
    def append(self, message: OutboxMessage) -> None:
        raise NotImplementedError


class TelemetryTransaction(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class ExecutionAttemptReader(Protocol):
    def get_context(self, execution_attempt_id: str) -> AttemptTelemetryContextDTO | None:
        raise NotImplementedError


class ExecutionEventRepository(Protocol):
    def add_many(self, events: list[ExecutionEventDTO]) -> tuple[list[ExecutionEventDTO], list[int]]:
        raise NotImplementedError

    def get_ack_sequences(self, execution_attempt_id: str) -> list[int]:
        raise NotImplementedError

    def list_events(
        self,
        execution_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        event_type: str | None = None,
        level: str | None = None,
    ) -> tuple[list[ExecutionEventDTO], str | None]:
        raise NotImplementedError

    def list_events_after_id(self, execution_id: str, event_id: str | None, limit: int = 100) -> list[ExecutionEventDTO]:
        raise NotImplementedError

    def list_logs(self, execution_id: str, *, limit: int = 200, cursor: str | None = None, level: str | None = None) -> tuple[list[ExecutionEventDTO], str | None]:
        raise NotImplementedError

    def latest_progress(self, execution_id: str) -> ExecutionProgressDTO:
        raise NotImplementedError

    def list_processes(self, execution_id: str) -> list[ExecutionProcessDTO]:
        raise NotImplementedError

    def count_for_execution(self, execution_id: str) -> tuple[int, int, datetime | None]:
        raise NotImplementedError


class EventAcknowledgementRepository(Protocol):
    def upsert(self, acknowledgement: EventAcknowledgementDTO) -> EventAcknowledgementDTO:
        raise NotImplementedError

    def get(self, execution_attempt_id: str) -> EventAcknowledgementDTO | None:
        raise NotImplementedError


class ExecutionMetricRepository(Protocol):
    def add_many(self, metrics: list[ExecutionMetricDTO]) -> None:
        raise NotImplementedError

    def list_for_execution(self, execution_id: str, *, limit: int = 200, metric_name: str | None = None) -> list[ExecutionMetricDTO]:
        raise NotImplementedError

    def count_for_execution(self, execution_id: str) -> int:
        raise NotImplementedError


class EventPayloadValidator(Protocol):
    def validate(self, event_type: str, payload: dict[str, Any], level: str | None = None) -> tuple[dict[str, Any], str | None, str | None]:
        raise NotImplementedError


class SecretMaskingPort(Protocol):
    def mask(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class RealtimePublisher(Protocol):
    def publish_execution_event(self, execution_id: str, event: ExecutionEventDTO) -> None:
        raise NotImplementedError

    def publish_execution_summary(self, summary: TelemetrySummaryDTO) -> None:
        raise NotImplementedError
