from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from modules.telemetry.domain.states import ExecutionMetricType


@dataclass(frozen=True)
class ExecutionMetric:
    id: str
    event_id: str
    execution_id: str
    task_execution_id: str
    execution_attempt_id: str
    metric_name: str
    metric_type: ExecutionMetricType
    value: float
    unit: str | None
    labels: dict[str, str] = field(default_factory=dict)
    occurred_at: datetime | None = None
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.metric_name:
            raise ValueError("ExecutionMetric requires metric_name.")
