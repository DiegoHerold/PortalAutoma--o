from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
)
from modules.telemetry.application.dto import (
    AttemptTelemetryContextDTO,
    EventAcknowledgementDTO,
    ExecutionEventDTO,
    ExecutionMetricDTO,
    ExecutionProcessDTO,
    ExecutionProgressDTO,
)
from modules.telemetry.infrastructure.orm.models import (
    EventAcknowledgementRecord,
    ExecutionEventRecord,
    ExecutionMetricRecord,
)


class SqlAlchemyTelemetryTransaction:
    def __init__(self, db: Session) -> None:
        self.db = db

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyExecutionAttemptTelemetryReader:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_context(self, execution_attempt_id: str) -> AttemptTelemetryContextDTO | None:
        row = self.db.execute(
            select(ExecutionAttemptRecord, TaskExecutionRecord, OrchestrationExecutionRecord)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .join(OrchestrationExecutionRecord, OrchestrationExecutionRecord.id == TaskExecutionRecord.execution_id)
            .where(ExecutionAttemptRecord.id == execution_attempt_id)
        ).one_or_none()
        if row is None:
            return None
        attempt, task, execution = row
        return AttemptTelemetryContextDTO(
            execution_id=execution.id,
            task_execution_id=task.id,
            execution_attempt_id=attempt.id,
            agent_id=attempt.agent_id,
            agent_instance_id=attempt.agent_instance_id,
            attempt_status=attempt.status,
            task_status=task.status,
            execution_status=execution.status,
        )


class SqlAlchemyExecutionEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_many(self, events: list[ExecutionEventDTO]) -> tuple[list[ExecutionEventDTO], list[int]]:
        if not events:
            return [], []
        rows = [_event_dict(event) for event in events]
        stmt = (
            insert(ExecutionEventRecord)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["execution_attempt_id", "event_sequence"])
            .returning(ExecutionEventRecord.event_sequence)
        )
        inserted_sequences = {int(seq) for seq in self.db.execute(stmt).scalars().all()}
        self.db.flush()
        inserted = [event for event in events if event.event_sequence in inserted_sequences]
        duplicates = sorted({event.event_sequence for event in events if event.event_sequence not in inserted_sequences})
        return inserted, duplicates

    def get_ack_sequences(self, execution_attempt_id: str) -> list[int]:
        rows = self.db.scalars(
            select(ExecutionEventRecord.event_sequence)
            .where(ExecutionEventRecord.execution_attempt_id == execution_attempt_id)
            .order_by(ExecutionEventRecord.event_sequence)
        ).all()
        return [int(item) for item in rows]

    def list_events(
        self,
        execution_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        event_type: str | None = None,
        level: str | None = None,
    ) -> tuple[list[ExecutionEventDTO], str | None]:
        stmt = select(ExecutionEventRecord).where(ExecutionEventRecord.execution_id == execution_id)
        stmt = self._apply_cursor(stmt, execution_id, cursor)
        if event_type:
            stmt = stmt.where(ExecutionEventRecord.event_type == event_type)
        if level:
            stmt = stmt.where(ExecutionEventRecord.level == level.upper())
        rows = self.db.scalars(stmt.order_by(ExecutionEventRecord.received_at, ExecutionEventRecord.id).limit(limit + 1)).all()
        next_cursor = rows[limit].id if len(rows) > limit else None
        return [_event_to_dto(row) for row in rows[:limit]], next_cursor

    def list_events_after_id(self, execution_id: str, event_id: str | None, limit: int = 100) -> list[ExecutionEventDTO]:
        if not event_id:
            return []
        stmt = select(ExecutionEventRecord).where(ExecutionEventRecord.execution_id == execution_id)
        stmt = self._apply_cursor(stmt, execution_id, event_id)
        rows = self.db.scalars(stmt.order_by(ExecutionEventRecord.received_at, ExecutionEventRecord.id).limit(limit)).all()
        return [_event_to_dto(row) for row in rows]

    def list_logs(self, execution_id: str, *, limit: int = 200, cursor: str | None = None, level: str | None = None) -> tuple[list[ExecutionEventDTO], str | None]:
        stmt = select(ExecutionEventRecord).where(
            ExecutionEventRecord.execution_id == execution_id,
            ExecutionEventRecord.event_type.in_(["log", "warning", "error"]),
        )
        stmt = self._apply_cursor(stmt, execution_id, cursor)
        if level:
            stmt = stmt.where(ExecutionEventRecord.level == level.upper())
        rows = self.db.scalars(stmt.order_by(ExecutionEventRecord.received_at, ExecutionEventRecord.id).limit(limit + 1)).all()
        next_cursor = rows[limit].id if len(rows) > limit else None
        return [_event_to_dto(row) for row in rows[:limit]], next_cursor

    def latest_progress(self, execution_id: str) -> ExecutionProgressDTO:
        row = self.db.scalars(
            select(ExecutionEventRecord)
            .where(
                ExecutionEventRecord.execution_id == execution_id,
                ExecutionEventRecord.event_type == "task.progress",
            )
            .order_by(ExecutionEventRecord.received_at.desc(), ExecutionEventRecord.event_sequence.desc())
            .limit(1)
        ).first()
        if row is None:
            return ExecutionProgressDTO(
                execution_id=execution_id,
                task_execution_id=None,
                execution_attempt_id=None,
                percentage=None,
                current=None,
                total=None,
                message=None,
                updated_at=None,
            )
        payload = row.payload or {}
        current = _number_or_none(payload.get("current"))
        total = _number_or_none(payload.get("total"))
        percentage = _number_or_none(payload.get("percentage") if "percentage" in payload else payload.get("progress"))
        if percentage is None and current is not None and total and total > 0:
            percentage = max(0.0, min(100.0, current / total * 100.0))
        return ExecutionProgressDTO(
            execution_id=execution_id,
            task_execution_id=row.task_execution_id,
            execution_attempt_id=row.execution_attempt_id,
            percentage=percentage,
            current=current,
            total=total,
            message=str(payload.get("message")) if payload.get("message") is not None else row.message,
            updated_at=row.received_at,
        )

    def list_processes(self, execution_id: str) -> list[ExecutionProcessDTO]:
        rows = self.db.scalars(
            select(ExecutionEventRecord)
            .where(
                ExecutionEventRecord.execution_id == execution_id,
                ExecutionEventRecord.event_type.in_(["process.started", "process.exited"]),
            )
            .order_by(ExecutionEventRecord.occurred_at, ExecutionEventRecord.event_sequence)
        ).all()
        processes: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = row.payload or {}
            process_id = str(payload.get("process_id") or payload.get("id") or row.id)
            entry = processes.setdefault(
                process_id,
                {
                    "process_id": process_id,
                    "execution_id": row.execution_id,
                    "execution_attempt_id": row.execution_attempt_id,
                    "name": None,
                    "command": None,
                    "status": "running",
                    "pid": None,
                    "exit_code": None,
                    "started_at": None,
                    "exited_at": None,
                },
            )
            if row.event_type == "process.started":
                entry.update(
                    {
                        "name": payload.get("name"),
                        "command": payload.get("command"),
                        "status": "running",
                        "pid": _int_or_none(payload.get("pid")),
                        "started_at": row.occurred_at,
                    }
                )
            else:
                entry.update(
                    {
                        "status": "exited",
                        "exit_code": _int_or_none(payload.get("exit_code")),
                        "exited_at": row.occurred_at,
                    }
                )
        return [ExecutionProcessDTO(**entry) for entry in processes.values()]

    def count_for_execution(self, execution_id: str) -> tuple[int, int, datetime | None]:
        event_count = self.db.scalar(select(func.count()).select_from(ExecutionEventRecord).where(ExecutionEventRecord.execution_id == execution_id)) or 0
        log_count = self.db.scalar(
            select(func.count())
            .select_from(ExecutionEventRecord)
            .where(
                ExecutionEventRecord.execution_id == execution_id,
                ExecutionEventRecord.event_type.in_(["log", "warning", "error"]),
            )
        ) or 0
        latest = self.db.scalar(
            select(func.max(ExecutionEventRecord.received_at)).where(ExecutionEventRecord.execution_id == execution_id)
        )
        return int(event_count), int(log_count), latest

    def _apply_cursor(self, stmt, execution_id: str, cursor: str | None):
        if not cursor:
            return stmt
        cursor_row = self.db.get(ExecutionEventRecord, cursor)
        if cursor_row is None or cursor_row.execution_id != execution_id:
            return stmt
        return stmt.where(
            or_(
                ExecutionEventRecord.received_at > cursor_row.received_at,
                and_(ExecutionEventRecord.received_at == cursor_row.received_at, ExecutionEventRecord.id > cursor_row.id),
            )
        )


class SqlAlchemyEventAcknowledgementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, acknowledgement: EventAcknowledgementDTO) -> EventAcknowledgementDTO:
        payload = {
            "execution_attempt_id": acknowledgement.execution_attempt_id,
            "highest_received_sequence": acknowledgement.highest_received_sequence,
            "highest_contiguous_sequence": acknowledgement.highest_contiguous_sequence,
            "missing_ranges": acknowledgement.missing_ranges,
            "duplicate_sequences": acknowledgement.duplicate_sequences,
            "updated_at": acknowledgement.updated_at or datetime.utcnow(),
        }
        stmt = (
            insert(EventAcknowledgementRecord)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=["execution_attempt_id"],
                set_={
                    "highest_received_sequence": payload["highest_received_sequence"],
                    "highest_contiguous_sequence": payload["highest_contiguous_sequence"],
                    "missing_ranges": payload["missing_ranges"],
                    "duplicate_sequences": payload["duplicate_sequences"],
                    "updated_at": payload["updated_at"],
                },
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        return self.get(acknowledgement.execution_attempt_id) or acknowledgement

    def get(self, execution_attempt_id: str) -> EventAcknowledgementDTO | None:
        row = self.db.get(EventAcknowledgementRecord, execution_attempt_id)
        if row is None:
            return None
        return EventAcknowledgementDTO(
            execution_attempt_id=row.execution_attempt_id,
            highest_received_sequence=row.highest_received_sequence,
            highest_contiguous_sequence=row.highest_contiguous_sequence,
            missing_ranges=list(row.missing_ranges or []),
            duplicate_sequences=list(row.duplicate_sequences or []),
            updated_at=row.updated_at,
        )


class SqlAlchemyExecutionMetricRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_many(self, metrics: list[ExecutionMetricDTO]) -> None:
        if not metrics:
            return
        stmt = (
            insert(ExecutionMetricRecord)
            .values([_metric_dict(metric) for metric in metrics])
            .on_conflict_do_nothing(index_elements=["execution_attempt_id", "event_sequence", "metric_name"])
        )
        self.db.execute(stmt)
        self.db.flush()

    def list_for_execution(self, execution_id: str, *, limit: int = 200, metric_name: str | None = None) -> list[ExecutionMetricDTO]:
        stmt = select(ExecutionMetricRecord).where(ExecutionMetricRecord.execution_id == execution_id)
        if metric_name:
            stmt = stmt.where(ExecutionMetricRecord.metric_name == metric_name)
        rows = self.db.scalars(stmt.order_by(ExecutionMetricRecord.received_at.desc()).limit(limit)).all()
        return [_metric_to_dto(row) for row in rows]

    def count_for_execution(self, execution_id: str) -> int:
        count = self.db.scalar(select(func.count()).select_from(ExecutionMetricRecord).where(ExecutionMetricRecord.execution_id == execution_id)) or 0
        return int(count)


def _event_dict(event: ExecutionEventDTO) -> dict[str, Any]:
    return {
        "id": event.id,
        "execution_id": event.execution_id,
        "task_execution_id": event.task_execution_id,
        "execution_attempt_id": event.execution_attempt_id,
        "agent_id": event.agent_id,
        "agent_instance_id": event.agent_instance_id,
        "event_sequence": event.event_sequence,
        "event_type": event.event_type,
        "level": event.level,
        "message": event.message,
        "payload": event.payload or {},
        "occurred_at": event.occurred_at,
        "received_at": event.received_at,
        "message_id": event.message_id,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
    }


def _event_to_dto(row: ExecutionEventRecord) -> ExecutionEventDTO:
    return ExecutionEventDTO(
        id=row.id,
        execution_id=row.execution_id,
        task_execution_id=row.task_execution_id,
        execution_attempt_id=row.execution_attempt_id,
        agent_id=row.agent_id,
        agent_instance_id=row.agent_instance_id,
        event_sequence=row.event_sequence,
        event_type=row.event_type,
        level=row.level,
        message=row.message,
        payload=row.payload or {},
        occurred_at=row.occurred_at,
        received_at=row.received_at,
        message_id=row.message_id,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
    )


def _metric_dict(metric: ExecutionMetricDTO) -> dict[str, Any]:
    return metric.__dict__.copy()


def _metric_to_dto(row: ExecutionMetricRecord) -> ExecutionMetricDTO:
    return ExecutionMetricDTO(
        id=row.id,
        event_id=row.event_id,
        execution_id=row.execution_id,
        task_execution_id=row.task_execution_id,
        execution_attempt_id=row.execution_attempt_id,
        event_sequence=row.event_sequence,
        metric_name=row.metric_name,
        metric_type=row.metric_type,
        value=row.value,
        unit=row.unit,
        labels=row.labels or {},
        occurred_at=row.occurred_at,
        received_at=row.received_at,
    )


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
