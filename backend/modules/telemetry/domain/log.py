from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.telemetry.domain.states import ExecutionLogLevel


@dataclass(frozen=True)
class ExecutionLog:
    event_id: str
    execution_id: str
    execution_attempt_id: str
    level: ExecutionLogLevel
    message: str
    occurred_at: datetime
    received_at: datetime

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("ExecutionLog requires a message.")
