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
    requirements_snapshot: dict[str, Any] | None = None
    available_at: datetime | None = None
    scheduling_attempts: int = 0
    last_scheduling_attempt_at: datetime | None = None
    next_scheduling_attempt_at: datetime | None = None
    last_scheduling_failure: dict[str, Any] | None = None

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
        requirements_snapshot: dict[str, Any] | None = None,
        retry_policy: dict[str, Any] | None = None,
        timeout_policy: dict[str, Any] | None = None,
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
            retry_policy=retry_policy or {"max_attempts": 1, "max_retries": 0},
            timeout_policy=timeout_policy or {"execution_timeout_seconds": timeout_seconds},
            created_at=now,
            requirements_snapshot=requirements_snapshot or {},
            available_at=now,
        )

    def mark_ready(self, now: datetime) -> "TaskExecution":
        return self._transition(TaskExecutionStatus.READY, ready_at=now)

    def mark_queued(self, now: datetime) -> "TaskExecution":
        return self._transition(TaskExecutionStatus.QUEUED, queued_at=now)

    def mark_retry_ready(self, now: datetime, available_at: datetime, failure: dict[str, Any] | None = None) -> "TaskExecution":
        return replace(
            self,
            status=TaskExecutionStatus.READY,
            ready_at=now,
            available_at=available_at,
            last_scheduling_failure=failure,
        )

    def record_scheduling_failure(self, now: datetime, next_at: datetime, failure: dict[str, Any]) -> "TaskExecution":
        return replace(
            self,
            available_at=next_at,
            scheduling_attempts=self.scheduling_attempts + 1,
            last_scheduling_attempt_at=now,
            next_scheduling_attempt_at=next_at,
            last_scheduling_failure=failure,
        )

    def record_scheduled(self, now: datetime, attempt_number: int) -> "TaskExecution":
        return replace(
            self,
            status=TaskExecutionStatus.QUEUED,
            queued_at=self.queued_at or now,
            current_attempt_number=attempt_number,
            scheduling_attempts=self.scheduling_attempts + 1,
            last_scheduling_attempt_at=now,
            next_scheduling_attempt_at=None,
            last_scheduling_failure=None,
        )

    def mark_running(self, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.RUNNING:
            return self
        return self._transition(TaskExecutionStatus.RUNNING, started_at=self.started_at or now)

    def mark_cancelling(self, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.CANCELLING:
            return self
        return self._transition(TaskExecutionStatus.CANCELLING, started_at=self.started_at or now)

    def mark_succeeded(self, *, result: dict[str, Any] | None, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.SUCCEEDED:
            return self
        return self._transition(TaskExecutionStatus.SUCCEEDED, result=result, completed_at=self.completed_at or now)

    def mark_failed(self, *, summary: str | None, result: dict[str, Any] | None, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.FAILED:
            return self
        return self._transition(TaskExecutionStatus.FAILED, result=result, failure_summary=summary, completed_at=self.completed_at or now)

    def mark_cancelled(self, *, summary: str | None, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.CANCELLED:
            return self
        return self._transition(TaskExecutionStatus.CANCELLED, failure_summary=summary, completed_at=self.completed_at or now)

    def mark_timed_out(self, *, summary: str | None, now: datetime) -> "TaskExecution":
        if self.status == TaskExecutionStatus.TIMED_OUT:
            return self
        return self._transition(TaskExecutionStatus.TIMED_OUT, failure_summary=summary, completed_at=self.completed_at or now)

    def _transition(self, status: TaskExecutionStatus, **changes: Any) -> "TaskExecution":
        if status not in TASK_EXECUTION_TRANSITIONS.get(self.status, set()):
            raise InvalidExecutionTransition(f"TaskExecution cannot transition from {self.status} to {status}.")
        return replace(self, status=status, **changes)
