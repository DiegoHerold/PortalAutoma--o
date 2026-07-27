from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from modules.orchestration.domain.errors import InvalidExecutionTransition
from modules.orchestration.domain.states import TASK_EXECUTION_TRANSITIONS, TaskExecutionStatus


@dataclass(frozen=True)
class TaskExecution:
    id: str
    execution_id: str
    automation_version_id: int
    status: TaskExecutionStatus
    priority: int
    parameters: dict[str, Any]
    input: dict[str, Any]
    result: dict[str, Any] | None
    retry_policy: dict[str, Any]
    timeout_policy: dict[str, Any]
    created_at: datetime
    ready_at: datetime | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_attempt_number: int = 0
    failure_summary: str | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        execution_id: str,
        automation_version_id: int,
        priority: int,
        parameters: dict[str, Any],
        input: dict[str, Any],
        timeout_seconds: int,
        now: datetime,
    ) -> "TaskExecution":
        if automation_version_id <= 0:
            raise ValueError("TaskExecution requires an AutomationVersion.")
        return cls(
            id=id,
            execution_id=execution_id,
            automation_version_id=automation_version_id,
            status=TaskExecutionStatus.PENDING,
            priority=priority,
            parameters=parameters,
            input=input,
            result=None,
            retry_policy={"max_retries": 0},
            timeout_policy={"timeout_seconds": timeout_seconds},
            created_at=now,
        )

    def mark_ready(self, now: datetime) -> "TaskExecution":
        return self._transition(TaskExecutionStatus.READY, ready_at=now)

    def mark_queued(self, now: datetime) -> "TaskExecution":
        return self._transition(TaskExecutionStatus.QUEUED, queued_at=now)

    def mark_running(self, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.RUNNING:
            return self
        return self._transition(TaskExecutionStatus.RUNNING, started_at=self.started_at or now)

    def _transition(self, status: TaskExecutionStatus, **changes: Any) -> "TaskExecution":
        if status not in TASK_EXECUTION_TRANSITIONS.get(self.status, set()):
            raise InvalidExecutionTransition(f"TaskExecution cannot transition from {self.status} to {status}.")
        return replace(self, status=status, **changes)
