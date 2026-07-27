from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from modules.orchestration.domain.errors import InvalidExecutionTransition
from modules.orchestration.domain.execution_attempt import ExecutionAttempt
from modules.orchestration.domain.states import (
    EXECUTION_TRANSITIONS,
    ExecutionAttemptStatus,
    ExecutionOrigin,
    ExecutionStatus,
    ExecutionType,
    TaskExecutionStatus,
)
from modules.orchestration.domain.task_execution import TaskExecution


@dataclass(frozen=True)
class Execution:
    id: str
    type: ExecutionType
    origin: ExecutionOrigin
    status: ExecutionStatus
    requested_by: str | None
    organization_id: str | None
    input: dict[str, Any]
    result: dict[str, Any] | None
    correlation_id: str | None
    idempotency_key: str | None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_summary: str | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        origin: ExecutionOrigin,
        requested_by: str | None,
        organization_id: str | None,
        input: dict[str, Any],
        correlation_id: str | None,
        idempotency_key: str | None,
        now: datetime,
    ) -> "Execution":
        return cls(
            id=id,
            type=ExecutionType.AUTOMATION,
            origin=origin,
            status=ExecutionStatus.CREATED,
            requested_by=requested_by,
            organization_id=organization_id,
            input=input,
            result=None,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            created_at=now,
        )

    def mark_pending(self) -> "Execution":
        return self._transition(ExecutionStatus.PENDING)

    def mark_running(self, now: datetime) -> "Execution":
        if self.status == ExecutionStatus.RUNNING:
            return self
        return self._transition(ExecutionStatus.RUNNING, started_at=self.started_at or now)

    def _transition(self, status: ExecutionStatus, **changes: Any) -> "Execution":
        if status not in EXECUTION_TRANSITIONS.get(self.status, set()):
            raise InvalidExecutionTransition(f"Execution cannot transition from {self.status} to {status}.")
        return replace(self, status=status, **changes)


__all__ = [
    "Execution",
    "ExecutionAttempt",
    "ExecutionAttemptStatus",
    "ExecutionOrigin",
    "ExecutionStatus",
    "ExecutionType",
    "TaskExecution",
    "TaskExecutionStatus",
]
