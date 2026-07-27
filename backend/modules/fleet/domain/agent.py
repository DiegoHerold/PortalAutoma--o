from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AgentConnectivityStatus(StrEnum):
    CONNECTING = "connecting"
    ONLINE = "online"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    OFFLINE = "offline"


class AgentAdministrativeStatus(StrEnum):
    PENDING_REGISTRATION = "pending_registration"
    ENABLED = "enabled"
    DRAINING = "draining"
    MAINTENANCE = "maintenance"
    UPDATING = "updating"
    DISABLED = "disabled"


class AgentHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class AgentOccupancyStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    SATURATED = "saturated"


@dataclass
class Agent:
    id: str
    name: str
    hostname: str
    enabled: bool = True
    connectivity_status: AgentConnectivityStatus = AgentConnectivityStatus.OFFLINE
    administrative_status: AgentAdministrativeStatus = AgentAdministrativeStatus.ENABLED
    health_status: AgentHealthStatus = AgentHealthStatus.HEALTHY
    occupancy_status: AgentOccupancyStatus = AgentOccupancyStatus.IDLE
    current_version: str | None = None
    desired_version: str | None = None
    protocol_version: str | None = None
    local_identity: str | None = None
    machine_fingerprint: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None
    disabled_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def connectivity(self) -> AgentConnectivityStatus:
        return self.connectivity_status

    @property
    def health(self) -> AgentHealthStatus:
        return self.health_status

    def ensure_can_connect(self) -> None:
        if not self.enabled or self.administrative_status == AgentAdministrativeStatus.DISABLED:
            from modules.fleet.domain.errors import AgentDisabledError

            raise AgentDisabledError("Agent is disabled.")

    def mark_connected(self, now: datetime, protocol_version: str) -> None:
        self.ensure_can_connect()
        self.connectivity_status = AgentConnectivityStatus.ONLINE
        self.protocol_version = protocol_version
        self.last_seen_at = now

    def mark_seen(self, now: datetime, health: AgentHealthStatus | None = None, current_version: str | None = None) -> None:
        self.connectivity_status = AgentConnectivityStatus.ONLINE
        self.last_seen_at = now
        if health is not None:
            self.health_status = health
        if current_version:
            self.current_version = current_version

    def mark_disconnected(self, now: datetime) -> None:
        self.connectivity_status = AgentConnectivityStatus.DISCONNECTED
        self.last_seen_at = now

    def mark_stale(self) -> None:
        if self.connectivity_status == AgentConnectivityStatus.ONLINE:
            self.connectivity_status = AgentConnectivityStatus.STALE

    def mark_offline(self) -> None:
        if self.connectivity_status in {AgentConnectivityStatus.ONLINE, AgentConnectivityStatus.STALE, AgentConnectivityStatus.DISCONNECTED}:
            self.connectivity_status = AgentConnectivityStatus.OFFLINE

    def disable(self, now: datetime) -> None:
        self.enabled = False
        self.administrative_status = AgentAdministrativeStatus.DISABLED
        self.connectivity_status = AgentConnectivityStatus.OFFLINE
        self.disabled_at = now

    def enable(self) -> None:
        self.enabled = True
        self.administrative_status = AgentAdministrativeStatus.ENABLED
        self.disabled_at = None

    def set_draining(self) -> None:
        if self.administrative_status == AgentAdministrativeStatus.DISABLED:
            from modules.fleet.domain.errors import InvalidAgentStateTransition

            raise InvalidAgentStateTransition("Disabled agents cannot be set to draining.")
        self.administrative_status = AgentAdministrativeStatus.DRAINING

    def set_maintenance(self, enabled: bool) -> None:
        if self.administrative_status == AgentAdministrativeStatus.DISABLED:
            from modules.fleet.domain.errors import InvalidAgentStateTransition

            raise InvalidAgentStateTransition("Disabled agents cannot enter maintenance.")
        self.administrative_status = AgentAdministrativeStatus.MAINTENANCE if enabled else AgentAdministrativeStatus.ENABLED


@dataclass
class AgentInstance:
    id: str
    agent_id: str
    process_started_at: datetime
    connected_at: datetime | None = None
    last_seen_at: datetime | None = None
    disconnected_at: datetime | None = None
    shutdown_reason: str | None = None
    agent_version: str | None = None
    negotiated_protocol_version: str | None = None
    connection_id: str | None = None
    created_at: datetime | None = None

    @property
    def protocol_version(self) -> str | None:
        return self.negotiated_protocol_version

    def connect(self, now: datetime, connection_id: str, protocol_version: str, agent_version: str | None = None) -> None:
        self.connected_at = now
        self.last_seen_at = now
        self.disconnected_at = None
        self.shutdown_reason = None
        self.connection_id = connection_id
        self.negotiated_protocol_version = protocol_version
        if agent_version:
            self.agent_version = agent_version

    def touch(self, now: datetime) -> None:
        self.last_seen_at = now

    def disconnect(self, now: datetime, reason: str | None = None) -> None:
        self.disconnected_at = now
        self.shutdown_reason = reason
