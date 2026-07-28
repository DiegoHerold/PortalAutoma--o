from __future__ import annotations

from modules.orchestration.domain.states import ExecutionStatus, TaskExecutionStatus


def calculate_execution_status(task_statuses: list[TaskExecutionStatus]) -> ExecutionStatus:
    if task_statuses and all(status == TaskExecutionStatus.SUCCEEDED for status in task_statuses):
        return ExecutionStatus.SUCCEEDED
    if any(status == TaskExecutionStatus.FAILED for status in task_statuses):
        return ExecutionStatus.FAILED
    if any(status == TaskExecutionStatus.TIMED_OUT for status in task_statuses):
        return ExecutionStatus.TIMED_OUT
    if any(status == TaskExecutionStatus.CANCELLED for status in task_statuses):
        return ExecutionStatus.CANCELLED
    if any(status == TaskExecutionStatus.RUNNING for status in task_statuses):
        return ExecutionStatus.RUNNING
    return ExecutionStatus.PENDING


def calculate_task_execution_status(attempt_running: bool, current_status: TaskExecutionStatus) -> TaskExecutionStatus:
    return TaskExecutionStatus.RUNNING if attempt_running else current_status
