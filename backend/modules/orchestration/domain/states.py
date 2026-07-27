from __future__ import annotations

from enum import StrEnum


class ExecutionType(StrEnum):
    AUTOMATION = "automation"
    FLOW = "flow"


class ExecutionOrigin(StrEnum):
    MANUAL = "manual"
    API = "api"
    SCHEDULE = "schedule"
    FLOW = "flow"
    RETRY = "retry"
    REPROCESS = "reprocess"
    SYSTEM = "system"


class ExecutionStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskExecutionStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class ExecutionAttemptStatus(StrEnum):
    CREATED = "created"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    COMMITTED = "committed"
    PREPARING = "preparing"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LOST = "lost"
    REJECTED = "rejected"
    EXPIRED = "expired"


EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.CREATED: {ExecutionStatus.PENDING},
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING},
    ExecutionStatus.RUNNING: set(),
}

TASK_EXECUTION_TRANSITIONS: dict[TaskExecutionStatus, set[TaskExecutionStatus]] = {
    TaskExecutionStatus.PENDING: {TaskExecutionStatus.READY},
    TaskExecutionStatus.READY: {TaskExecutionStatus.QUEUED},
    TaskExecutionStatus.QUEUED: {TaskExecutionStatus.RUNNING, TaskExecutionStatus.READY},
    TaskExecutionStatus.RUNNING: set(),
}

EXECUTION_ATTEMPT_TRANSITIONS: dict[ExecutionAttemptStatus, set[ExecutionAttemptStatus]] = {
    ExecutionAttemptStatus.CREATED: {ExecutionAttemptStatus.OFFERED},
    ExecutionAttemptStatus.OFFERED: {
        ExecutionAttemptStatus.ACCEPTED,
        ExecutionAttemptStatus.REJECTED,
        ExecutionAttemptStatus.EXPIRED,
    },
    ExecutionAttemptStatus.ACCEPTED: {ExecutionAttemptStatus.COMMITTED, ExecutionAttemptStatus.EXPIRED},
    ExecutionAttemptStatus.COMMITTED: {ExecutionAttemptStatus.PREPARING, ExecutionAttemptStatus.RUNNING},
    ExecutionAttemptStatus.PREPARING: {ExecutionAttemptStatus.RUNNING},
    ExecutionAttemptStatus.RUNNING: set(),
    ExecutionAttemptStatus.REJECTED: set(),
    ExecutionAttemptStatus.EXPIRED: set(),
}
