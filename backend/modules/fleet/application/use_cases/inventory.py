from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from modules.fleet.application.dto import CapabilityDTO, MachineProfileDTO
from modules.fleet.application.ports import (
    AgentCapabilityRepository,
    AgentConfigurationRepository,
    AgentMachineProfileRepository,
    AgentPoolRepository,
    AgentRepository,
    AgentResourceSnapshotRepository,
    FleetOutbox,
    TransactionManager,
)
from modules.fleet.application.use_cases._shared import apply_agent_update, calculate_pool, ensure_configuration, new_id, occupancy_from_pools, outbox, parse_datetime, utcnow
from modules.fleet.domain.errors import AgentNotFoundError, InvalidAgentInstanceError
from modules.fleet.domain.states import DEFAULT_AGENT_POOLS


class RecordAgentMachineProfile:
    def __init__(self, agents: AgentRepository, profiles: AgentMachineProfileRepository, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.profiles = profiles
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> MachineProfileDTO:
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        observed_at = parse_datetime(payload.get("observed_at"), utcnow())
        profile = self.profiles.add(
            MachineProfileDTO(
                id=new_id("amp"),
                agent_id=agent_id,
                agent_instance_id=agent_instance_id,
                hostname=str(payload.get("hostname") or agent.hostname),
                observed_at=observed_at,
                operating_system=payload.get("operating_system") or payload.get("os"),
                operating_system_version=payload.get("operating_system_version") or payload.get("os_version"),
                operating_system_build=payload.get("operating_system_build"),
                architecture=payload.get("architecture"),
                cpu_model=payload.get("cpu_model"),
                physical_cores=payload.get("physical_cores"),
                logical_processors=payload.get("logical_processors"),
                total_memory_mb=payload.get("total_memory_mb"),
                disk_volumes=payload.get("disk_volumes") or [],
                network_summary=payload.get("network_summary") or {},
                interactive_session_supported=payload.get("interactive_session_supported"),
                revision=int(payload.get("revision") or 1),
                expires_at=observed_at + timedelta(days=7),
            )
        )
        self.agents.save(
            apply_agent_update(
                agent,
                hostname=profile.hostname,
                machine_fingerprint=payload.get("machine_fingerprint") or agent.machine_fingerprint,
            )
        )
        outbox(self.outbox, "agent.profile.updated", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id, "profile_id": profile.id})
        self.transaction.commit()
        return profile


class RecordAgentCapabilities:
    def __init__(self, agents: AgentRepository, capabilities: AgentCapabilityRepository, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.capabilities = capabilities
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> list[CapabilityDTO]:
        if self.agents.get(agent_id) is None:
            raise AgentNotFoundError("Agent not found.")
        rows: list[CapabilityDTO] = []
        for item in payload.get("capabilities") or []:
            if not isinstance(item, dict) or not item.get("key"):
                continue
            observed_at = parse_datetime(item.get("observed_at"), utcnow())
            rows.append(
                CapabilityDTO(
                    id=new_id("acp"),
                    agent_id=agent_id,
                    agent_instance_id=agent_instance_id,
                    key=str(item["key"]),
                    status=str(item.get("status") or "unknown"),
                    version=item.get("version"),
                    attributes=item.get("attributes") or {},
                    source=item.get("source"),
                    observed_at=observed_at,
                    expires_at=parse_datetime(item.get("expires_at"), observed_at + timedelta(minutes=10)) if item.get("expires_at") else observed_at + timedelta(minutes=10),
                    revision=int(item.get("revision") or 1),
                )
            )
        saved = self.capabilities.replace_current(agent_id, rows)
        outbox(self.outbox, "agent.capabilities.updated", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id, "count": len(saved)})
        self.transaction.commit()
        return saved


class RecordAgentCapacity:
    def __init__(self, agents: AgentRepository, pools: AgentPoolRepository, configurations: AgentConfigurationRepository, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.pools = pools
        self.configurations = configurations
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> list:
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        if payload.get("agent_instance_id") not in (None, agent_instance_id):
            raise InvalidAgentInstanceError("Capacity update was sent by a different AgentInstance.")
        observed_at = parse_datetime(payload.get("observed_at"), utcnow())
        configuration = ensure_configuration(self.configurations, agent_id)
        pool_payload = payload.get("pools") or payload.get("capacity") or {}
        rows = [
            calculate_pool(agent_id, pool_type, observed_at, pool_payload.get(pool_type) or {}, configuration, int(payload.get("revision") or 1))
            for pool_type in DEFAULT_AGENT_POOLS
        ]
        saved = self.pools.replace_current(agent_id, rows)
        self.agents.save(apply_agent_update(agent, occupancy_status=occupancy_from_pools(saved)))
        outbox(self.outbox, "agent.capacity.updated", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id})
        self.transaction.commit()
        return saved


class GetAgentCapabilities:
    def __init__(self, capabilities: AgentCapabilityRepository) -> None:
        self.capabilities = capabilities

    def execute(self, agent_id: str) -> list[CapabilityDTO]:
        return self.capabilities.list_current(agent_id)


class GetAgentCapacity:
    def __init__(self, pools: AgentPoolRepository, snapshots: AgentResourceSnapshotRepository) -> None:
        self.pools = pools
        self.snapshots = snapshots

    def execute(self, agent_id: str) -> dict[str, Any]:
        return {
            "pools": self.pools.list_current(agent_id),
            "latest_resource_snapshot": self.snapshots.latest_for_agent(agent_id),
        }
