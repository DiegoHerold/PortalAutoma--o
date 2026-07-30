from __future__ import annotations

from enum import StrEnum


class ExecutionType(StrEnum):
    AUTOMATION = "automation"
    FLOW = "flow"


class ExecutionOrigin(StrEnum):
    MANUAL = "manual"
    API = "api"
    TRIGGER = "trigger"
    SCHEDULE = "schedule"
    FLOW = "flow"
    RETRY = "retry"
    REPROCESS = "reprocess"
    SYSTEM = "system"


class ExecutionStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskExecutionStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
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
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LOST = "lost"
    REJECTED = "rejected"
    EXPIRED = "expired"


EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.CREATED: {ExecutionStatus.PENDING},
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.CANCELLING,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.PARTIALLY_SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    },
    ExecutionStatus.CANCELLING: {
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
    },
    ExecutionStatus.SUCCEEDED: set(),
    ExecutionStatus.PARTIALLY_SUCCEEDED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
    ExecutionStatus.TIMED_OUT: set(),
}

TASK_EXECUTION_TRANSITIONS: dict[TaskExecutionStatus, set[TaskExecutionStatus]] = {
    TaskExecutionStatus.PENDING: {TaskExecutionStatus.READY},
    TaskExecutionStatus.READY: {TaskExecutionStatus.QUEUED, TaskExecutionStatus.CANCELLED},
    TaskExecutionStatus.QUEUED: {TaskExecutionStatus.RUNNING, TaskExecutionStatus.READY, TaskExecutionStatus.CANCELLED, TaskExecutionStatus.CANCELLING},
    TaskExecutionStatus.RUNNING: {
        TaskExecutionStatus.READY,
        TaskExecutionStatus.CANCELLING,
        TaskExecutionStatus.SUCCEEDED,
        TaskExecutionStatus.FAILED,
        TaskExecutionStatus.CANCELLED,
        TaskExecutionStatus.TIMED_OUT,
    },
    TaskExecutionStatus.CANCELLING: {
        TaskExecutionStatus.CANCELLED,
        TaskExecutionStatus.TIMED_OUT,
        TaskExecutionStatus.FAILED,
    },
    TaskExecutionStatus.SUCCEEDED: set(),
    TaskExecutionStatus.FAILED: set(),
    TaskExecutionStatus.CANCELLED: set(),
    TaskExecutionStatus.TIMED_OUT: set(),
    TaskExecutionStatus.SKIPPED: set(),
}

EXECUTION_ATTEMPT_TRANSITIONS: dict[ExecutionAttemptStatus, set[ExecutionAttemptStatus]] = {
    ExecutionAttemptStatus.CREATED: {ExecutionAttemptStatus.OFFERED},
    ExecutionAttemptStatus.OFFERED: {
        ExecutionAttemptStatus.ACCEPTED,
        ExecutionAttemptStatus.REJECTED,
        ExecutionAttemptStatus.EXPIRED,
    },
    ExecutionAttemptStatus.ACCEPTED: {ExecutionAttemptStatus.COMMITTED, ExecutionAttemptStatus.EXPIRED, ExecutionAttemptStatus.CANCEL_REQUESTED},
    ExecutionAttemptStatus.COMMITTED: {ExecutionAttemptStatus.PREPARING, ExecutionAttemptStatus.RUNNING, ExecutionAttemptStatus.CANCEL_REQUESTED},
    ExecutionAttemptStatus.PREPARING: {ExecutionAttemptStatus.RUNNING, ExecutionAttemptStatus.CANCEL_REQUESTED, ExecutionAttemptStatus.TIMED_OUT, ExecutionAttemptStatus.LOST},
    ExecutionAttemptStatus.RUNNING: {
        ExecutionAttemptStatus.CANCEL_REQUESTED,
        ExecutionAttemptStatus.SUCCEEDED,
        ExecutionAttemptStatus.FAILED,
        ExecutionAttemptStatus.CANCELLED,
        ExecutionAttemptStatus.TIMED_OUT,
        ExecutionAttemptStatus.LOST,
    },
    ExecutionAttemptStatus.CANCEL_REQUESTED: {
        ExecutionAttemptStatus.CANCELLED,
        ExecutionAttemptStatus.FAILED,
        ExecutionAttemptStatus.TIMED_OUT,
        ExecutionAttemptStatus.LOST,
    },
    ExecutionAttemptStatus.SUCCEEDED: set(),
    ExecutionAttemptStatus.FAILED: set(),
    ExecutionAttemptStatus.CANCELLED: set(),
    ExecutionAttemptStatus.TIMED_OUT: set(),
    ExecutionAttemptStatus.LOST: set(),
    ExecutionAttemptStatus.REJECTED: set(),
    ExecutionAttemptStatus.EXPIRED: set(),
}
