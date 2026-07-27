from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRecord(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id", ondelete="SET NULL"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    hostname: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    connectivity_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    administrative_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    health_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    occupancy_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    current_version: Mapped[str | None] = mapped_column(String(80))
    desired_version: Mapped[str | None] = mapped_column(String(80))
    protocol_version: Mapped[str | None] = mapped_column(String(20))
    local_identity: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    machine_fingerprint: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentInstanceRecord(Base):
    __tablename__ = "agent_instances"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    process_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    shutdown_reason: Mapped[str | None] = mapped_column(Text)
    agent_version: Mapped[str | None] = mapped_column(String(80))
    negotiated_protocol_version: Mapped[str | None] = mapped_column(String(20))
    connection_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRegistrationTokenRecord(Base):
    __tablename__ = "agent_registration_tokens"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class AgentCredentialRecord(Base):
    __tablename__ = "agent_credentials"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)
    public_identifier: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentMachineProfileRecord(Base):
    __tablename__ = "agent_machine_profiles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(180), nullable=False)
    operating_system: Mapped[str | None] = mapped_column(String(120))
    operating_system_version: Mapped[str | None] = mapped_column(String(120))
    operating_system_build: Mapped[str | None] = mapped_column(String(120))
    architecture: Mapped[str | None] = mapped_column(String(80))
    cpu_model: Mapped[str | None] = mapped_column(Text)
    physical_cores: Mapped[int | None] = mapped_column(Integer)
    logical_processors: Mapped[int | None] = mapped_column(Integer)
    total_memory_mb: Mapped[int | None] = mapped_column(Integer)
    disk_volumes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    network_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    interactive_session_supported: Mapped[bool | None] = mapped_column(Boolean)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentResourceSnapshotRecord(Base):
    __tablename__ = "agent_resource_snapshots"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    cpu_usage_percentage: Mapped[float | None] = mapped_column(Float)
    memory_total_mb: Mapped[int | None] = mapped_column(Integer)
    memory_available_mb: Mapped[int | None] = mapped_column(Integer)
    memory_usage_percentage: Mapped[float | None] = mapped_column(Float)
    disk_free_mb: Mapped[int | None] = mapped_column(Integer)
    disk_usage_percentage: Mapped[float | None] = mapped_column(Float)
    process_count: Mapped[int | None] = mapped_column(Integer)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentCapabilityRecord(Base):
    __tablename__ = "agent_capabilities"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    version: Mapped[str | None] = mapped_column(String(120))
    attributes_json: Mapped[dict] = mapped_column("attributes", JSONB, nullable=False, default=dict)
    source: Mapped[str | None] = mapped_column(String(120))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class AgentConfigurationRecord(Base):
    __tablename__ = "agent_configurations"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    heartbeat_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    stale_after_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    offline_after_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    administrator_pool_limits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled_pools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allowlist_capabilities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    maintenance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    desired_version: Mapped[str | None] = mapped_column(String(80))
    restrictions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentPoolRecord(Base):
    __tablename__ = "agent_pools"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    pool_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    recommended_total: Mapped[int | None] = mapped_column(Integer)
    administrator_total: Mapped[int | None] = mapped_column(Integer)
    effective_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class InteractiveSessionSnapshotRecord(Base):
    __tablename__ = "interactive_session_snapshots"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    available: Mapped[bool | None] = mapped_column(Boolean)
    locked: Mapped[bool | None] = mapped_column(Boolean)
    user: Mapped[str | None] = mapped_column(String(255))
    session_id: Mapped[str | None] = mapped_column(String(120))
    session_type: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentConnectionRecord(Base):
    __tablename__ = "agent_connections"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str] = mapped_column(ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    protocol_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    close_reason: Mapped[str | None] = mapped_column(Text)


class AgentDiagnosticRecord(Base):
    __tablename__ = "agent_diagnostics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_instance_id: Mapped[str | None] = mapped_column(ForeignKey("agent_instances.id", ondelete="SET NULL"), index=True)
    request_command_id: Mapped[str | None] = mapped_column(ForeignKey("agent_commands.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    artifact_id: Mapped[str | None] = mapped_column(String(80))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
