from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class AgentCommandRecord(Base):
    __tablename__ = "agent_commands"
    __table_args__ = (UniqueConstraint("agent_id", "command_sequence", name="uq_agent_command_agent_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    agent_instance_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    command_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    message_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class ExecutionOfferRecord(Base):
    __tablename__ = "execution_offers"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requirements_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_code: Mapped[str | None] = mapped_column(String(120))
    rejection_details: Mapped[dict | None] = mapped_column(JSONB)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    commit_token_hash: Mapped[str | None] = mapped_column(String(64))
    commit_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DispatchDecisionRecord(Base):
    __tablename__ = "dispatch_decisions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    scheduler_run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("execution_attempts.id", ondelete="SET NULL"), index=True)
    execution_offer_id: Mapped[str | None] = mapped_column(ForeignKey("execution_offers.id", ondelete="SET NULL"), index=True)
    selected_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    selected_agent_instance_id: Mapped[str | None] = mapped_column(ForeignKey("agent_instances.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class ResourceReservationRecord(Base):
    __tablename__ = "resource_reservations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    task_execution_id: Mapped[str | None] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=True, index=True)
    execution_offer_id: Mapped[str | None] = mapped_column(ForeignKey("execution_offers.id", ondelete="CASCADE"), nullable=True, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id"), nullable=False, index=True)
    pool_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class ResourceLockRecord(Base):
    __tablename__ = "resource_locks"
    __table_args__ = (
        Index(
            "uq_resource_locks_active_scope_key",
            "scope",
            "normalized_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    resource_key: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class ExecutionLeaseRecord(Base):
    __tablename__ = "execution_leases"
    __table_args__ = (
        Index(
            "uq_execution_leases_active_attempt",
            "execution_attempt_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'suspect')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewal_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grace_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(Text)


class RetryScheduleRecord(Base):
    __tablename__ = "retry_schedules"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CancellationRequestRecord(Base):
    __tablename__ = "cancellation_requests"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str | None] = mapped_column(ForeignKey("task_executions.id", ondelete="SET NULL"), index=True)
    execution_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("execution_attempts.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_by: Mapped[str | None] = mapped_column(String(120), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    graceful_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    force_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    command_id: Mapped[str | None] = mapped_column(ForeignKey("agent_commands.id", ondelete="SET NULL"), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    agent_instance_id: Mapped[str | None] = mapped_column(ForeignKey("agent_instances.id", ondelete="SET NULL"), index=True)
    execution_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("execution_attempts.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
