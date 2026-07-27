from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Execution:
    id: str
    type: ExecutionType
    origin: ExecutionOrigin
    status: ExecutionStatus


@dataclass(frozen=True)
class TaskExecution:
    id: str
    execution_id: str
    status: TaskExecutionStatus


@dataclass(frozen=True)
class ExecutionAttempt:
    id: str
    task_execution_id: str
    attempt_number: int
    status: ExecutionAttemptStatus

