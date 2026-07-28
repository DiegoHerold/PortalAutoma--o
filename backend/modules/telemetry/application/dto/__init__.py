from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AttemptTelemetryContextDTO:
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    attempt_status: str
    task_status: str
    execution_status: str


@dataclass(frozen=True)
class ExecutionEventDTO:
    id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    agent_id: str
    agent_instance_id: str
    event_sequence: int
    event_type: str
    level: str | None
    message: str | None
    payload: dict[str, Any]
    occurred_at: datetime
    received_at: datetime
    message_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None


@dataclass(frozen=True)
class ExecutionMetricDTO:
    id: str
    event_id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    event_sequence: int
    metric_name: str
    metric_type: str
    value: float
    unit: str | None
    labels: dict[str, str]
    occurred_at: datetime
    received_at: datetime


@dataclass(frozen=True)
class EventAcknowledgementDTO:
    execution_attempt_id: str
    highest_received_sequence: int
    highest_contiguous_sequence: int
    missing_ranges: list[dict[str, int]] = field(default_factory=list)
    duplicate_sequences: list[int] = field(default_factory=list)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class EventBatchCommand:
    execution_attempt_id: str
    events: list[dict[str, Any]]
    agent_id: str
    agent_instance_id: str
    message_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None


@dataclass(frozen=True)
class EventBatchAckDTO:
    message_type: str
    execution_attempt_id: str
    accepted_events: int
    duplicate_events: int
    acknowledgement: EventAcknowledgementDTO


@dataclass(frozen=True)
class ExecutionProgressDTO:
    execution_id: str
    task_execution_id: str | None
    execution_attempt_id: str | None
    percentage: float | None
    current: float | None
    total: float | None
    message: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ExecutionProcessDTO:
    process_id: str
    execution_id: str
    execution_attempt_id: str
    name: str | None
    command: str | None
    status: str
    pid: int | None
    exit_code: int | None
    started_at: datetime | None
    exited_at: datetime | None


@dataclass(frozen=True)
class TelemetrySummaryDTO:
    execution_id: str
    event_count: int
    log_count: int
    metric_count: int
    artifact_count: int
    latest_event_at: datetime | None
    progress_percentage: float | None


@dataclass(frozen=True)
class EventPageDTO:
    items: list[ExecutionEventDTO]
    next_cursor: str | None


def to_payload(value: Any) -> Any:
    if is_dataclass(value):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
