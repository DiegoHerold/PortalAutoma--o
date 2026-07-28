from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class OrchestrationExecutionRecord(Base):
    __tablename__ = "orchestration_executions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    origin: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_by: Mapped[str | None] = mapped_column(String(120), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(120), index=True)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    legacy_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), unique=True, nullable=True)


class TaskExecutionRecord(Base):
    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_version_id: Mapped[int] = mapped_column(ForeignKey("automation_versions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)
    retry_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timeout_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_summary: Mapped[str | None] = mapped_column(Text)
    requirements_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    scheduling_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_scheduling_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_scheduling_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_scheduling_failure: Mapped[dict | None] = mapped_column(JSONB)


class ExecutionAttemptRecord(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (UniqueConstraint("task_execution_id", "attempt_number", name="uq_execution_attempt_task_number"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    runtime_version_id: Mapped[str | None] = mapped_column(ForeignKey("runtime_versions.id"), nullable=True, index=True)
    package_id: Mapped[str | None] = mapped_column(ForeignKey("automation_packages.id"), nullable=True, index=True)
    offer_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preparing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    output: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    resource_usage: Mapped[dict | None] = mapped_column(JSONB)
