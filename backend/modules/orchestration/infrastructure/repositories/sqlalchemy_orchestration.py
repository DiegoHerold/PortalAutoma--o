from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.orchestration.application.dto import ExecutionAttemptDTO, ExecutionDTO, TaskExecutionDTO
from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
)
from modules.telemetry.infrastructure.orm.models import OutboxMessageRecord


class SqlAlchemyOrchestrationTransaction:
    def __init__(self, db: Session) -> None:
        self.db = db

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyOrchestrationOutbox:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> None:
        self.db.add(
            OutboxMessageRecord(
                id=str(uuid4()),
                topic="execution.events",
                message_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                status="pending",
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
        )
        self.db.flush()


class SqlAlchemyExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, execution: ExecutionDTO) -> ExecutionDTO:
        row = OrchestrationExecutionRecord(**_execution_dict(execution))
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def save(self, execution: ExecutionDTO) -> ExecutionDTO:
        row = self.db.get(OrchestrationExecutionRecord, execution.id)
        if row is None:
            return self.add(execution)
        for key, value in _execution_dict(execution).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)

    def get(self, execution_id: str) -> ExecutionDTO | None:
        row = self.db.get(OrchestrationExecutionRecord, execution_id)
        return _execution_to_dto(row) if row else None

    def list(self, limit: int = 100, offset: int = 0) -> list[ExecutionDTO]:
        rows = self.db.scalars(
            select(OrchestrationExecutionRecord)
            .order_by(OrchestrationExecutionRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return [_execution_to_dto(row) for row in rows]

    def link_legacy_job(self, execution_id: str, legacy_job_id: int) -> ExecutionDTO | None:
        row = self.db.get(OrchestrationExecutionRecord, execution_id)
        if row is None:
            return None
        row.legacy_job_id = legacy_job_id
        self.db.add(row)
        self.db.flush()
        return _execution_to_dto(row)


class SqlAlchemyTaskExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        row = TaskExecutionRecord(**_task_dict(task))
        self.db.add(row)
        self.db.flush()
        return _task_to_dto(row)

    def save(self, task: TaskExecutionDTO) -> TaskExecutionDTO:
        row = self.db.get(TaskExecutionRecord, task.id)
        if row is None:
            return self.add(task)
        for key, value in _task_dict(task).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _task_to_dto(row)

    def get(self, task_execution_id: str) -> TaskExecutionDTO | None:
        row = self.db.get(TaskExecutionRecord, task_execution_id)
        return _task_to_dto(row) if row else None

    def list_for_execution(self, execution_id: str) -> list[TaskExecutionDTO]:
        rows = self.db.scalars(
            select(TaskExecutionRecord)
            .where(TaskExecutionRecord.execution_id == execution_id)
            .order_by(TaskExecutionRecord.created_at)
        ).all()
        return [_task_to_dto(row) for row in rows]


class SqlAlchemyExecutionAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, attempt: ExecutionAttemptDTO) -> ExecutionAttemptDTO:
        row = ExecutionAttemptRecord(**_attempt_dict(attempt))
        self.db.add(row)
        self.db.flush()
        return _attempt_to_dto(row)

    def save(self, attempt: ExecutionAttemptDTO) -> ExecutionAttemptDTO:
        row = self.db.get(ExecutionAttemptRecord, attempt.id)
        if row is None:
            return self.add(attempt)
        for key, value in _attempt_dict(attempt).items():
            setattr(row, key, value)
        self.db.add(row)
        self.db.flush()
        return _attempt_to_dto(row)

    def get(self, execution_attempt_id: str) -> ExecutionAttemptDTO | None:
        row = self.db.get(ExecutionAttemptRecord, execution_attempt_id)
        return _attempt_to_dto(row) if row else None

    def next_attempt_number(self, task_execution_id: str) -> int:
        current = self.db.scalar(
            select(func.max(ExecutionAttemptRecord.attempt_number)).where(
                ExecutionAttemptRecord.task_execution_id == task_execution_id
            )
        )
        return int(current or 0) + 1

    def list_for_execution(self, execution_id: str) -> list[ExecutionAttemptDTO]:
        rows = self.db.scalars(
            select(ExecutionAttemptRecord)
            .join(TaskExecutionRecord, TaskExecutionRecord.id == ExecutionAttemptRecord.task_execution_id)
            .where(TaskExecutionRecord.execution_id == execution_id)
            .order_by(ExecutionAttemptRecord.attempt_number)
        ).all()
        return [_attempt_to_dto(row) for row in rows]


def _execution_dict(execution: ExecutionDTO) -> dict[str, Any]:
    return {
        "id": execution.id,
        "type": execution.type,
        "origin": execution.origin,
        "status": execution.status,
        "requested_by": execution.requested_by,
        "organization_id": execution.organization_id,
        "input": execution.input or {},
        "result": execution.result,
        "correlation_id": execution.correlation_id,
        "idempotency_key": execution.idempotency_key,
        "created_at": execution.created_at,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "failure_summary": execution.failure_summary,
        "legacy_job_id": execution.legacy_job_id,
    }


def _task_dict(task: TaskExecutionDTO) -> dict[str, Any]:
    return task.__dict__.copy()


def _attempt_dict(attempt: ExecutionAttemptDTO) -> dict[str, Any]:
    return attempt.__dict__.copy()


def _execution_to_dto(row: OrchestrationExecutionRecord) -> ExecutionDTO:
    return ExecutionDTO(
        id=row.id,
        type=row.type,
        origin=row.origin,
        status=row.status,
        requested_by=row.requested_by,
        organization_id=row.organization_id,
        input=row.input or {},
        result=row.result,
        correlation_id=row.correlation_id,
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        failure_summary=row.failure_summary,
        legacy_job_id=row.legacy_job_id,
    )


def _task_to_dto(row: TaskExecutionRecord) -> TaskExecutionDTO:
    return TaskExecutionDTO(
        id=row.id,
        execution_id=row.execution_id,
        automation_version_id=row.automation_version_id,
        status=row.status,
        priority=row.priority,
        parameters=row.parameters or {},
        input=row.input or {},
        result=row.result,
        retry_policy=row.retry_policy or {},
        timeout_policy=row.timeout_policy or {},
        created_at=row.created_at,
        ready_at=row.ready_at,
        queued_at=row.queued_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        current_attempt_number=row.current_attempt_number,
        failure_summary=row.failure_summary,
    )


def _attempt_to_dto(row: ExecutionAttemptRecord) -> ExecutionAttemptDTO:
    return ExecutionAttemptDTO(
        id=row.id,
        task_execution_id=row.task_execution_id,
        attempt_number=row.attempt_number,
        agent_id=row.agent_id,
        agent_instance_id=row.agent_instance_id,
        status=row.status,
        runtime_version_id=row.runtime_version_id,
        package_id=row.package_id,
        offer_id=row.offer_id,
        created_at=row.created_at,
        offered_at=row.offered_at,
        accepted_at=row.accepted_at,
        committed_at=row.committed_at,
        preparing_at=row.preparing_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        error_code=row.error_code,
        error_message=row.error_message,
    )
