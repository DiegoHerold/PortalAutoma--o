from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from modules.telemetry.domain.states import ExecutionEventType, ExecutionLogLevel


@dataclass(frozen=True)
class ExecutionEvent:
    id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    agent_id: str | None
    agent_instance_id: str | None
    event_sequence: int
    event_type: ExecutionEventType
    level: ExecutionLogLevel | None
    message: str | None
    occurred_at: datetime
    received_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    executor_type: str = "agent"
    executor_id: str | None = None

    def __post_init__(self) -> None:
        if self.event_sequence <= 0:
            raise ValueError("ExecutionEvent event_sequence must be positive.")
        if not self.execution_id or not self.task_execution_id or not self.execution_attempt_id:
            raise ValueError("ExecutionEvent requires execution, task and attempt identifiers.")
        if self.executor_type == "direct":
            if not self.executor_id:
                raise ValueError("ExecutionEvent do modo direto requer a instância direta.")
        elif not self.agent_id or not self.agent_instance_id:
            raise ValueError("ExecutionEvent requires Agent and AgentInstance identifiers.")
