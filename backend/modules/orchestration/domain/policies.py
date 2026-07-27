from __future__ import annotations

from modules.orchestration.domain.states import ExecutionStatus, TaskExecutionStatus


def calculate_execution_status(task_statuses: list[TaskExecutionStatus]) -> ExecutionStatus:
    if any(status == TaskExecutionStatus.RUNNING for status in task_statuses):
        return ExecutionStatus.RUNNING
    return ExecutionStatus.PENDING


def calculate_task_execution_status(attempt_running: bool, current_status: TaskExecutionStatus) -> TaskExecutionStatus:
    return TaskExecutionStatus.RUNNING if attempt_running else current_status
