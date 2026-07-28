from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class OutboxMessageRecord(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class InboxMessageRecord(Base):
    __tablename__ = "inbox_messages"

    message_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    message_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class ExecutionEventRecord(Base):
    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "event_sequence", name="uq_execution_events_attempt_sequence"),
        Index("ix_execution_events_execution_received", "execution_id", "received_at"),
        Index("ix_execution_events_task_received", "task_execution_id", "received_at"),
        Index("ix_execution_events_attempt_sequence", "execution_attempt_id", "event_sequence"),
        Index("ix_execution_events_agent_received", "agent_id", "received_at"),
        Index("ix_execution_events_type_received", "event_type", "received_at"),
        Index("ix_execution_events_level_received", "level", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id"), nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    level: Mapped[str | None] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(120), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(120), index=True)


class EventAcknowledgementRecord(Base):
    __tablename__ = "event_acknowledgements"

    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True)
    highest_received_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    highest_contiguous_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_ranges: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    duplicate_sequences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExecutionMetricRecord(Base):
    __tablename__ = "execution_metrics"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "event_sequence", "metric_name", name="uq_execution_metrics_attempt_sequence_name"),
        Index("ix_execution_metrics_execution_received", "execution_id", "received_at"),
        Index("ix_execution_metrics_attempt_name_received", "execution_attempt_id", "metric_name", "received_at"),
        Index("ix_execution_metrics_name_received", "metric_name", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("execution_events.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    labels: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
