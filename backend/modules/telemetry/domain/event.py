from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExecutionEventType(StrEnum):
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_TIMED_OUT = "execution.timed_out"
    LOG = "log"
    WARNING = "warning"
    ERROR = "error"
    METRIC = "metric"
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_AVAILABLE = "artifact.available"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class ExecutionEvent:
    id: str
    execution_attempt_id: str
    event_sequence: int
    event_type: ExecutionEventType
    occurred_at: datetime
    payload: dict[str, Any]

