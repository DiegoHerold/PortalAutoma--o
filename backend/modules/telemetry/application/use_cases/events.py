from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from modules.telemetry.application.dto import (
    AttemptTelemetryContextDTO,
    EventAcknowledgementDTO,
    EventBatchAckDTO,
    EventBatchCommand,
    EventPageDTO,
    ExecutionEventDTO,
    ExecutionMetricDTO,
    ExecutionProgressDTO,
    TelemetrySummaryDTO,
)
from modules.telemetry.application.ports import (
    EventAcknowledgementRepository,
    EventPayloadValidator,
    ExecutionAttemptReader,
    ExecutionEventRepository,
    ExecutionMetricRepository,
    RealtimePublisher,
    SecretMaskingPort,
    TelemetryTransaction,
)
from modules.telemetry.domain.errors import (
    ExecutionAttemptTelemetryError,
    TelemetryValidationError,
)
from modules.telemetry.domain.states import ExecutionEventType, ExecutionMetricType


# Limites do contrato automation-events/v1: 500 eventos por lote e 64 KB por evento.
MAX_EVENTS_PER_BATCH = 500
MAX_EVENT_PAYLOAD_BYTES = 64 * 1024
MAX_BATCH_BYTES = 1_000_000
TERMINAL_ATTEMPT_STATUSES = {"succeeded", "failed", "cancelled", "timed_out", "lost", "rejected", "expired"}


class IngestExecutionEventBatch:
    def __init__(
        self,
        attempts: ExecutionAttemptReader,
        events: ExecutionEventRepository,
        acknowledgements: EventAcknowledgementRepository,
        metrics: ExecutionMetricRepository,
        validator: EventPayloadValidator,
        masker: SecretMaskingPort,
        realtime: RealtimePublisher,
        transaction: TelemetryTransaction,
        projector: object | None = None,
    ) -> None:
        self.projector = projector
        self.attempts = attempts
        self.events = events
        self.acknowledgements = acknowledgements
        self.metrics = metrics
        self.validator = validator
        self.masker = masker
        self.realtime = realtime
        self.transaction = transaction

    def execute(self, command: EventBatchCommand) -> EventBatchAckDTO:
        try:
            context, telemetry_events = self._build_events(command)
            inserted, duplicate_sequences = self.events.add_many(telemetry_events)
            if self.projector is not None:
                # Só os inseridos: repetição não projeta duas vezes (idempotência).
                self.projector.execute(context, inserted)
            metrics = _metrics_for_events(inserted)
            self.metrics.add_many(metrics)
            acknowledgement = self.acknowledgements.upsert(
                _compute_ack(
                    command.execution_attempt_id,
                    self.events.get_ack_sequences(command.execution_attempt_id),
                    duplicate_sequences,
                )
            )
            event_count, log_count, latest_event_at = self.events.count_for_execution(telemetry_events[0].execution_id)
            metric_count = self.metrics.count_for_execution(telemetry_events[0].execution_id)
            progress = self.events.latest_progress(telemetry_events[0].execution_id)
            summary = TelemetrySummaryDTO(
                execution_id=telemetry_events[0].execution_id,
                event_count=event_count,
                log_count=log_count,
                metric_count=metric_count,
                artifact_count=0,
                latest_event_at=latest_event_at,
                progress_percentage=progress.percentage,
            )
            self.transaction.commit()
        except Exception:
            self.transaction.rollback()
            raise

        for event in inserted:
            self.realtime.publish_execution_event(event.execution_id, event)
        self.realtime.publish_execution_summary(summary)
        return EventBatchAckDTO(
            message_type="execution.event.ack",
            execution_attempt_id=command.execution_attempt_id,
            accepted_events=len(inserted),
            duplicate_events=len(duplicate_sequences),
            acknowledgement=acknowledgement,
        )

    def _build_events(self, command: EventBatchCommand) -> tuple[AttemptTelemetryContextDTO, list[ExecutionEventDTO]]:
        if not command.execution_attempt_id:
            raise TelemetryValidationError("execution_attempt_id is required.")
        if not isinstance(command.events, list) or not command.events:
            raise TelemetryValidationError("events must be a non-empty array.")
        if len(command.events) > MAX_EVENTS_PER_BATCH:
            raise TelemetryValidationError(f"Event batch cannot exceed {MAX_EVENTS_PER_BATCH} events.")
        if len(json.dumps(command.events, ensure_ascii=False, default=str).encode("utf-8")) > MAX_BATCH_BYTES:
            raise TelemetryValidationError("Event batch payload is too large.")

        context = self.attempts.get_context(command.execution_attempt_id)
        if context is None:
            raise ExecutionAttemptTelemetryError("ExecutionAttempt not found.")
        if command.executor_type == "direct":
            if context.executor_type != "direct" or not command.executor_id or context.executor_id != command.executor_id:
                raise ExecutionAttemptTelemetryError("ExecutionAttempt belongs to another executor.")
        elif context.executor_type != "agent" or context.agent_id != command.agent_id \
                or context.agent_instance_id != command.agent_instance_id:
            raise ExecutionAttemptTelemetryError("ExecutionAttempt belongs to another Agent or AgentInstance.")

        sequences = [_required_int(event, "event_sequence") for event in command.events]
        if len(set(sequences)) != len(sequences):
            raise TelemetryValidationError("Event batch cannot contain repeated event_sequence values.")
        if context.attempt_status in TERMINAL_ATTEMPT_STATUSES:
            existing = set(self.events.get_ack_sequences(command.execution_attempt_id))
            if not set(sequences).issubset(existing):
                raise ExecutionAttemptTelemetryError("ExecutionAttempt is terminal and cannot receive new events.")

        received_at = utcnow()
        telemetry_events: list[ExecutionEventDTO] = []
        for raw_event in command.events:
            _validate_event_shape(raw_event)
            payload = raw_event["payload"]
            if len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
                raise TelemetryValidationError("Event payload is too large.")
            event_type = str(raw_event["event_type"])
            normalized_payload, level, message = self.validator.validate(event_type, payload, raw_event.get("level"))
            telemetry_events.append(
                ExecutionEventDTO(
                    id=str(raw_event["event_id"]),
                    execution_id=context.execution_id,
                    task_execution_id=context.task_execution_id,
                    execution_attempt_id=context.execution_attempt_id,
                    agent_id=context.agent_id,
                    agent_instance_id=context.agent_instance_id,
                    event_sequence=int(raw_event["event_sequence"]),
                    event_type=event_type,
                    level=level,
                    message=message,
                    payload=self.masker.mask(normalized_payload),
                    occurred_at=parse_datetime(raw_event["occurred_at"], received_at),
                    received_at=received_at,
                    message_id=command.message_id,
                    correlation_id=command.correlation_id,
                    causation_id=command.causation_id,
                    executor_type=context.executor_type,
                    executor_id=context.executor_id,
                )
            )
        return context, telemetry_events


class GetExecutionEvents:
    def __init__(self, events: ExecutionEventRepository) -> None:
        self.events = events

    def execute(self, execution_id: str, *, limit: int = 100, cursor: str | None = None, event_type: str | None = None, level: str | None = None) -> EventPageDTO:
        items, next_cursor = self.events.list_events(
            execution_id,
            limit=limit,
            cursor=cursor,
            event_type=event_type,
            level=level,
        )
        return EventPageDTO(items=items, next_cursor=next_cursor)


class GetExecutionLogs:
    def __init__(self, events: ExecutionEventRepository) -> None:
        self.events = events

    def execute(self, execution_id: str, *, limit: int = 200, cursor: str | None = None, level: str | None = None) -> EventPageDTO:
        items, next_cursor = self.events.list_logs(execution_id, limit=limit, cursor=cursor, level=level)
        return EventPageDTO(items=items, next_cursor=next_cursor)


class GetExecutionTimeline:
    def __init__(self, events: ExecutionEventRepository) -> None:
        self.events = events

    def execute(self, execution_id: str, *, limit: int = 300, cursor: str | None = None) -> EventPageDTO:
        items, next_cursor = self.events.list_events(execution_id, limit=limit, cursor=cursor)
        return EventPageDTO(items=items, next_cursor=next_cursor)


class GetExecutionMetrics:
    def __init__(self, metrics: ExecutionMetricRepository) -> None:
        self.metrics = metrics

    def execute(self, execution_id: str, *, limit: int = 200, metric_name: str | None = None) -> list[ExecutionMetricDTO]:
        return self.metrics.list_for_execution(execution_id, limit=limit, metric_name=metric_name)


class GetExecutionProgress:
    def __init__(self, events: ExecutionEventRepository) -> None:
        self.events = events

    def execute(self, execution_id: str) -> ExecutionProgressDTO:
        return self.events.latest_progress(execution_id)


class GetExecutionProcesses:
    def __init__(self, events: ExecutionEventRepository) -> None:
        self.events = events

    def execute(self, execution_id: str):
        return self.events.list_processes(execution_id)


class GetTelemetrySummary:
    def __init__(self, events: ExecutionEventRepository, metrics: ExecutionMetricRepository) -> None:
        self.events = events
        self.metrics = metrics

    def execute(self, execution_id: str, artifact_count: int = 0) -> TelemetrySummaryDTO:
        event_count, log_count, latest = self.events.count_for_execution(execution_id)
        progress = self.events.latest_progress(execution_id)
        return TelemetrySummaryDTO(
            execution_id=execution_id,
            event_count=event_count,
            log_count=log_count,
            metric_count=self.metrics.count_for_execution(execution_id),
            artifact_count=artifact_count,
            latest_event_at=latest,
            progress_percentage=progress.percentage,
        )


def _compute_ack(execution_attempt_id: str, sequences: list[int], duplicate_sequences: list[int]) -> EventAcknowledgementDTO:
    ordered = sorted(set(sequences))
    highest_received = max(ordered, default=0)
    contiguous = 0
    for sequence in ordered:
        if sequence == contiguous + 1:
            contiguous = sequence
        elif sequence > contiguous + 1:
            break
    gaps: list[dict[str, int]] = []
    expected = contiguous + 1
    for sequence in ordered:
        if sequence <= contiguous:
            continue
        if sequence > expected:
            gaps.append({"from": expected, "to": sequence - 1})
        expected = sequence + 1
    return EventAcknowledgementDTO(
        execution_attempt_id=execution_attempt_id,
        highest_received_sequence=highest_received,
        highest_contiguous_sequence=contiguous,
        missing_ranges=gaps,
        duplicate_sequences=duplicate_sequences,
        updated_at=utcnow(),
    )


def _metrics_for_events(events: list[ExecutionEventDTO]) -> list[ExecutionMetricDTO]:
    metrics: list[ExecutionMetricDTO] = []
    for event in events:
        payload = event.payload or {}
        if event.event_type == ExecutionEventType.METRIC.value:
            metric_type = str(payload.get("metric_type") or ExecutionMetricType.GAUGE.value)
            metrics.append(
                ExecutionMetricDTO(
                    id=new_id("met"),
                    event_id=event.id,
                    execution_id=event.execution_id,
                    task_execution_id=event.task_execution_id,
                    execution_attempt_id=event.execution_attempt_id,
                    event_sequence=event.event_sequence,
                    metric_name=str(payload["metric_name"]),
                    metric_type=metric_type,
                    value=float(payload["value"]),
                    unit=str(payload.get("unit")) if payload.get("unit") is not None else None,
                    labels={str(key): str(value) for key, value in (payload.get("labels") or {}).items()},
                    occurred_at=event.occurred_at,
                    received_at=event.received_at,
                )
            )
        elif event.event_type == ExecutionEventType.TASK_PROGRESS.value:
            percentage = payload.get("percentage") if "percentage" in payload else payload.get("progress")
            if percentage is None and payload.get("current") is not None and payload.get("total"):
                total = float(payload["total"])
                percentage = (float(payload["current"]) / total * 100.0) if total > 0 else None
            if percentage is not None:
                metrics.append(
                    ExecutionMetricDTO(
                        id=new_id("met"),
                        event_id=event.id,
                        execution_id=event.execution_id,
                        task_execution_id=event.task_execution_id,
                        execution_attempt_id=event.execution_attempt_id,
                        event_sequence=event.event_sequence,
                        metric_name="progress_percentage",
                        metric_type=ExecutionMetricType.GAUGE.value,
                        value=float(percentage),
                        unit="percent",
                        labels={},
                        occurred_at=event.occurred_at,
                        received_at=event.received_at,
                    )
                )
    return metrics


def _validate_event_shape(raw_event: dict[str, Any]) -> None:
    if not isinstance(raw_event, dict):
        raise TelemetryValidationError("Each event must be an object.")
    allowed = {"event_id", "event_sequence", "event_type", "occurred_at", "level", "payload"}
    extra = set(raw_event) - allowed
    if extra:
        raise TelemetryValidationError(f"Event contains unsupported fields: {', '.join(sorted(extra))}.")
    required = {"event_id", "event_sequence", "event_type", "occurred_at", "payload"}
    missing = [field for field in sorted(required) if raw_event.get(field) in (None, "")]
    if missing:
        raise TelemetryValidationError(f"Event is missing fields: {', '.join(missing)}.")
    _required_int(raw_event, "event_sequence")


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool):
        raise TelemetryValidationError(f"{field} must be an integer.")
    try:
        converted = int(value)
    except (TypeError, ValueError) as exc:
        raise TelemetryValidationError(f"{field} must be an integer.") from exc
    if converted <= 0:
        raise TelemetryValidationError(f"{field} must be positive.")
    return converted


def parse_datetime(value: Any, default: datetime) -> datetime:
    """Sempre em UTC com fuso. Sem o fuso, o PostgreSQL lê o horário no fuso da sessão
    (America/Sao_Paulo no portal) e grava o evento 3 horas adiantado."""
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            convertido = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TelemetryValidationError(f"Invalid date-time: {value}.") from exc
        return convertido.astimezone(UTC) if convertido.tzinfo is not None else convertido.replace(tzinfo=UTC)
    return default


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(UTC)
