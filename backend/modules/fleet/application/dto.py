from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ActorDTO:
    actor_type: str
    actor_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class AgentDTO:
    id: str
    name: str
    hostname: str
    enabled: bool
    connectivity_status: str
    administrative_status: str
    health_status: str
    occupancy_status: str
    current_version: str | None
    desired_version: str | None
    protocol_version: str | None
    created_at: datetime | None
    updated_at: datetime | None
    last_seen_at: datetime | None
    disabled_at: datetime | None
    local_identity: str | None = None
    machine_fingerprint: str | None = None
    worker_id: int | None = None
    cpu_percentage: float | None = None
    memory_percentage: float | None = None
    disk_free_mb: int | None = None
    interactive_session: dict[str, Any] | None = None
    pools: dict[str, dict[str, Any]] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentInstanceDTO:
    id: str
    agent_id: str
    process_started_at: datetime
    connected_at: datetime | None
    last_seen_at: datetime | None
    disconnected_at: datetime | None
    shutdown_reason: str | None
    agent_version: str | None
    negotiated_protocol_version: str | None
    connection_id: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class RegistrationTokenDTO:
    id: str
    status: str
    expires_at: datetime
    created_by: str | None
    created_at: datetime
    token: str | None = None
    used_at: datetime | None = None
    used_by_agent_id: str | None = None
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentCredentialDTO:
    id: str
    agent_id: str
    credential_type: str
    public_identifier: str
    status: str
    issued_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    rotated_at: datetime | None
    revoked_at: datetime | None
    secret: str | None = None


@dataclass(frozen=True)
class RegistrationResultDTO:
    agent: AgentDTO
    credential: AgentCredentialDTO
    heartbeat_interval_seconds: int
    stale_after_seconds: int
    offline_after_seconds: int


@dataclass(frozen=True)
class MachineProfileDTO:
    id: str
    agent_id: str
    agent_instance_id: str
    hostname: str
    observed_at: datetime
    operating_system: str | None = None
    operating_system_version: str | None = None
    operating_system_build: str | None = None
    architecture: str | None = None
    cpu_model: str | None = None
    physical_cores: int | None = None
    logical_processors: int | None = None
    total_memory_mb: int | None = None
    disk_volumes: list[dict[str, Any]] = field(default_factory=list)
    network_summary: dict[str, Any] = field(default_factory=dict)
    interactive_session_supported: bool | None = None
    revision: int = 1
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ResourceSnapshotDTO:
    id: str
    agent_id: str
    agent_instance_id: str
    observed_at: datetime
    cpu_usage_percentage: float | None = None
    memory_total_mb: int | None = None
    memory_available_mb: int | None = None
    memory_usage_percentage: float | None = None
    disk_free_mb: int | None = None
    disk_usage_percentage: float | None = None
    process_count: int | None = None
    uptime_seconds: int | None = None
    revision: int = 1
    expires_at: datetime | None = None


@dataclass(frozen=True)
class CapabilityDTO:
    key: str
    status: str
    observed_at: datetime
    id: str | None = None
    agent_id: str | None = None
    agent_instance_id: str | None = None
    version: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    source: str | None = None
    revision: int = 1


@dataclass(frozen=True)
class AgentPoolDTO:
    agent_id: str
    pool_type: str
    observed_at: datetime
    recommended_total: int | None
    administrator_total: int | None
    effective_total: int
    used: int
    reserved: int
    available: int
    revision: int


@dataclass(frozen=True)
class AgentConfigurationDTO:
    agent_id: str
    heartbeat_interval_seconds: int
    stale_after_seconds: int
    offline_after_seconds: int
    administrator_pool_limits: dict[str, int | None]
    enabled_pools: list[str]
    allowlist_capabilities: list[str]
    maintenance: bool
    desired_version: str | None
    restrictions: dict[str, Any]
    updated_at: datetime | None


@dataclass(frozen=True)
class InteractiveSessionDTO:
    agent_id: str
    agent_instance_id: str
    available: bool | None
    locked: bool | None
    observed_at: datetime
    user: str | None = None
    session_id: str | None = None
    session_type: str | None = None
    expires_at: datetime | None = None
    state: str = "unknown"


@dataclass(frozen=True)
class AgentDiagnosticDTO:
    id: str
    agent_id: str
    status: str
    requested_at: datetime
    agent_instance_id: str | None = None
    request_command_id: str | None = None
    summary: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifact_id: str | None = None
    completed_at: datetime | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentCommandDTO:
    id: str
    agent_id: str
    agent_instance_id: str | None
    command_sequence: int
    message_type: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    available_at: datetime
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    expires_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None
