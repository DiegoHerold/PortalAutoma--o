from __future__ import annotations

from enum import StrEnum


class ExecutionEventType(StrEnum):
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_TIMED_OUT = "execution.timed_out"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    LOG = "log"
    WARNING = "warning"
    ERROR = "error"
    METRIC = "metric"
    PROCESS_STARTED = "process.started"
    PROCESS_EXITED = "process.exited"
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_AVAILABLE = "artifact.available"
    ARTIFACT_FAILED = "artifact.failed"
    DIAGNOSTIC = "diagnostic"
    # Evento da automacao (contracts/automation-events/v1), igual no modo agente e no direto.
    AUTOMATION_EVENT = "automation.event"


class ExecutionLogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExecutionMetricType(StrEnum):
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM_SAMPLE = "histogram_sample"


class TerminalExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
