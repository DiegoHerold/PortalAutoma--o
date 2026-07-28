from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FlowDTO:
    id: str
    key: str
    name: str
    description: str | None
    category_id: int | None
    tags: list[str]
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime | None = None


@dataclass(frozen=True)
class FlowVersionDTO:
    id: str
    flow_id: str
    version: str
    status: str
    definition: dict[str, Any]
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any] | None
    release_notes: str | None
    created_by: str | None
    created_at: datetime
    published_by: str | None = None
    published_at: datetime | None = None
    deprecated_at: datetime | None = None
    blocked_at: datetime | None = None


@dataclass(frozen=True)
class FlowNodeDTO:
    id: str
    flow_version_id: str
    key: str
    name: str
    node_type: str
    automation_version_id: int | None
    configuration: dict[str, Any]
    input_mapping: dict[str, Any]
    output_mapping: dict[str, Any]
    condition: dict[str, Any] | None
    retry_policy: dict[str, Any]
    timeout_policy: dict[str, Any]
    failure_policy: str
    execution_policy: dict[str, Any]
    position_metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class FlowEdgeDTO:
    id: str
    flow_version_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    condition: dict[str, Any] | None
    mapping: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class FlowExecutionDTO:
    id: str
    execution_id: str
    flow_version_id: str
    status: str
    origin: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    requested_by: str | None
    schedule_execution_id: str | None
    correlation_id: str | None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    failure_summary: str | None = None


@dataclass(frozen=True)
class FlowNodeExecutionDTO:
    id: str
    flow_execution_id: str
    flow_node_id: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    condition_result: dict[str, Any] | None
    dependency_state: dict[str, Any]
    revision: int
    task_execution_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    skipped_at: datetime | None = None
    failure_summary: str | None = None


@dataclass(frozen=True)
class FlowValidationIssueDTO:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowValidationResultDTO:
    valid: bool
    issues: list[FlowValidationIssueDTO]
    topological_order: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlowExecutionDetailsDTO:
    flow_execution: FlowExecutionDTO
    execution: dict[str, Any] | None
    flow_version: FlowVersionDTO | None
    nodes: list[FlowNodeDTO]
    edges: list[FlowEdgeDTO]
    node_executions: list[FlowNodeExecutionDTO]

    def to_payload(self) -> dict[str, Any]:
        return to_payload(self)


def to_payload(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return to_payload(asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_payload(item) for item in value]
    return value
