from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FlowCreateRequest(BaseModel):
    key: str
    name: str
    description: str | None = None
    category_id: int | None = None
    tags: list[str] = Field(default_factory=list)


class FlowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: int | None = None
    tags: list[str] | None = None
    status: str | None = None


class FlowVersionCreateRequest(BaseModel):
    version: str
    definition: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    release_notes: str | None = None


class FlowVersionUpdateRequest(BaseModel):
    definition: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    release_notes: str | None = None


class FlowNodeRequest(BaseModel):
    key: str
    name: str | None = None
    node_type: str = "automation"
    automation_version_id: int | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_mapping: dict[str, Any] = Field(default_factory=dict)
    condition: dict[str, Any] | None = None
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    timeout_policy: dict[str, Any] = Field(default_factory=dict)
    failure_policy: str = "fail_flow"
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    position_metadata: dict[str, Any] = Field(default_factory=dict)


class FlowNodeUpdateRequest(BaseModel):
    """Corpo do PATCH /flow-nodes/{id} — todos os campos opcionais (key não é editável)."""

    name: str | None = None
    node_type: str | None = None
    automation_version_id: int | None = None
    configuration: dict[str, Any] | None = None
    input_mapping: dict[str, Any] | None = None
    output_mapping: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    retry_policy: dict[str, Any] | None = None
    timeout_policy: dict[str, Any] | None = None
    failure_policy: str | None = None
    execution_policy: dict[str, Any] | None = None
    position_metadata: dict[str, Any] | None = None


class FlowEdgeRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str = "success"
    condition: dict[str, Any] | None = None
    mapping: dict[str, Any] = Field(default_factory=dict)


class FlowExecutionCreateRequest(BaseModel):
    flow_version_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    origin: str = "manual"


class FlowCancelRequest(BaseModel):
    reason: str | None = None
