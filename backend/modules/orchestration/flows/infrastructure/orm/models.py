from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FlowRecord(Base):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class FlowVersionRecord(Base):
    __tablename__ = "flow_versions"
    __table_args__ = (UniqueConstraint("flow_id", "version", name="uq_flow_versions_flow_version"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    flow_id: Mapped[str] = mapped_column(ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_schema: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    release_notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FlowNodeRecord(Base):
    __tablename__ = "flow_nodes"
    __table_args__ = (UniqueConstraint("flow_version_id", "key", name="uq_flow_nodes_version_key"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    flow_version_id: Mapped[str] = mapped_column(ForeignKey("flow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    automation_version_id: Mapped[int | None] = mapped_column(ForeignKey("automation_versions.id"), nullable=True, index=True)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    condition: Mapped[dict | None] = mapped_column(JSONB)
    retry_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timeout_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failure_policy: Mapped[str] = mapped_column(String(60), nullable=False, default="fail_flow")
    execution_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    position_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FlowEdgeRecord(Base):
    __tablename__ = "flow_edges"
    __table_args__ = (UniqueConstraint("flow_version_id", "source_node_id", "target_node_id", "edge_type", name="uq_flow_edges_version_source_target_type"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    flow_version_id: Mapped[str] = mapped_column(ForeignKey("flow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("flow_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("flow_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(40), nullable=False, default="success")
    condition: Mapped[dict | None] = mapped_column(JSONB)
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FlowExecutionRecord(Base):
    __tablename__ = "flow_executions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    flow_version_id: Mapped[str] = mapped_column(ForeignKey("flow_versions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB)
    requested_by: Mapped[str | None] = mapped_column(String(120), index=True)
    schedule_execution_id: Mapped[str | None] = mapped_column(String(80), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)


class FlowNodeExecutionRecord(Base):
    __tablename__ = "flow_node_executions"
    __table_args__ = (UniqueConstraint("flow_execution_id", "flow_node_id", name="uq_flow_node_executions_flow_node"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    flow_execution_id: Mapped[str] = mapped_column(ForeignKey("flow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    flow_node_id: Mapped[str] = mapped_column(ForeignKey("flow_nodes.id"), nullable=False, index=True)
    task_execution_id: Mapped[str | None] = mapped_column(ForeignKey("task_executions.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB)
    condition_result: Mapped[dict | None] = mapped_column(JSONB)
    dependency_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
