from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from modules.fleet.application.dto import (
    AgentCommandDTO,
    AgentConfigurationDTO,
    AgentCredentialDTO,
    AgentDTO,
    AgentDiagnosticDTO,
    AgentInstanceDTO,
    AgentPoolDTO,
    CapabilityDTO,
    InteractiveSessionDTO,
    MachineProfileDTO,
    RegistrationTokenDTO,
    ResourceSnapshotDTO,
)


class TransactionManager(Protocol):
    def flush(self) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class FleetOutbox(Protocol):
    def append_event(self, event_type: str, aggregate_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class AgentRepository(Protocol):
    def add(self, agent: AgentDTO) -> AgentDTO:
        raise NotImplementedError

    def save(self, agent: AgentDTO) -> AgentDTO:
        raise NotImplementedError

    def get(self, agent_id: str) -> AgentDTO | None:
        raise NotImplementedError

    def get_by_local_identity(self, local_identity: str) -> AgentDTO | None:
        raise NotImplementedError

    def get_by_machine_fingerprint(self, machine_fingerprint: str) -> AgentDTO | None:
        raise NotImplementedError

    def get_by_worker_id(self, worker_id: int) -> AgentDTO | None:
        raise NotImplementedError

    def list(self) -> list[AgentDTO]:
        raise NotImplementedError


class AgentInstanceRepository(Protocol):
    def add(self, instance: AgentInstanceDTO) -> AgentInstanceDTO:
        raise NotImplementedError

    def save(self, instance: AgentInstanceDTO) -> AgentInstanceDTO:
        raise NotImplementedError

    def get(self, instance_id: str) -> AgentInstanceDTO | None:
        raise NotImplementedError

    def get_current(self, agent_id: str) -> AgentInstanceDTO | None:
        raise NotImplementedError

    def list_for_agent(self, agent_id: str) -> list[AgentInstanceDTO]:
        raise NotImplementedError

    def disconnect_active_for_agent(self, agent_id: str, now: datetime, reason: str) -> None:
        raise NotImplementedError


class AgentRegistrationTokenRepository(Protocol):
    def add(self, token: RegistrationTokenDTO, token_hash: str) -> RegistrationTokenDTO:
        raise NotImplementedError

    def get(self, token_id: str) -> RegistrationTokenDTO | None:
        raise NotImplementedError

    def get_by_hash(self, token_hash: str) -> RegistrationTokenDTO | None:
        raise NotImplementedError

    def save(self, token: RegistrationTokenDTO) -> RegistrationTokenDTO:
        raise NotImplementedError


class AgentCredentialRepository(Protocol):
    def add(self, credential: AgentCredentialDTO, secret_hash: str) -> AgentCredentialDTO:
        raise NotImplementedError

    def get(self, credential_id: str) -> AgentCredentialDTO | None:
        raise NotImplementedError

    def get_by_public_identifier(self, public_identifier: str) -> tuple[AgentCredentialDTO, str] | None:
        raise NotImplementedError

    def save(self, credential: AgentCredentialDTO) -> AgentCredentialDTO:
        raise NotImplementedError

    def active_for_agent(self, agent_id: str) -> list[AgentCredentialDTO]:
        raise NotImplementedError


class AgentMachineProfileRepository(Protocol):
    def add(self, profile: MachineProfileDTO) -> MachineProfileDTO:
        raise NotImplementedError

    def latest_for_agent(self, agent_id: str) -> MachineProfileDTO | None:
        raise NotImplementedError


class AgentResourceSnapshotRepository(Protocol):
    def add(self, snapshot: ResourceSnapshotDTO) -> ResourceSnapshotDTO:
        raise NotImplementedError

    def latest_for_agent(self, agent_id: str) -> ResourceSnapshotDTO | None:
        raise NotImplementedError


class AgentCapabilityRepository(Protocol):
    def replace_current(self, agent_id: str, capabilities: list[CapabilityDTO]) -> list[CapabilityDTO]:
        raise NotImplementedError

    def list_current(self, agent_id: str) -> list[CapabilityDTO]:
        raise NotImplementedError


class AgentConfigurationRepository(Protocol):
    def get(self, agent_id: str) -> AgentConfigurationDTO | None:
        raise NotImplementedError

    def save(self, configuration: AgentConfigurationDTO) -> AgentConfigurationDTO:
        raise NotImplementedError


class AgentPoolRepository(Protocol):
    def replace_current(self, agent_id: str, pools: list[AgentPoolDTO]) -> list[AgentPoolDTO]:
        raise NotImplementedError

    def list_current(self, agent_id: str) -> list[AgentPoolDTO]:
        raise NotImplementedError


class InteractiveSessionRepository(Protocol):
    def add(self, snapshot: InteractiveSessionDTO) -> InteractiveSessionDTO:
        raise NotImplementedError

    def latest_for_agent(self, agent_id: str) -> InteractiveSessionDTO | None:
        raise NotImplementedError


class AgentConnectionRepository(Protocol):
    def open(self, connection_id: str, agent_id: str, agent_instance_id: str, connected_at: datetime, protocol_version: str) -> None:
        raise NotImplementedError

    def close(self, connection_id: str, disconnected_at: datetime, reason: str | None) -> None:
        raise NotImplementedError

    def close_active_for_agent(self, agent_id: str, disconnected_at: datetime, reason: str) -> None:
        raise NotImplementedError


class AgentDiagnosticRepository(Protocol):
    def add(self, diagnostic: AgentDiagnosticDTO) -> AgentDiagnosticDTO:
        raise NotImplementedError

    def save_result(self, diagnostic: AgentDiagnosticDTO) -> AgentDiagnosticDTO:
        raise NotImplementedError

    def list_for_agent(self, agent_id: str) -> list[AgentDiagnosticDTO]:
        raise NotImplementedError


class AgentCommandRepository(Protocol):
    def create(self, agent_id: str, message_type: str, payload: dict[str, Any], expires_at: datetime | None = None) -> AgentCommandDTO:
        raise NotImplementedError

    def pending_for_agent(self, agent_id: str, limit: int) -> list[AgentCommandDTO]:
        raise NotImplementedError

    def mark_sent(self, command_id: str, agent_instance_id: str, sent_at: datetime) -> AgentCommandDTO | None:
        raise NotImplementedError

    def acknowledge(self, agent_id: str, command_id: str, command_sequence: int | None, status: str, acknowledged_at: datetime) -> AgentCommandDTO | None:
        raise NotImplementedError
