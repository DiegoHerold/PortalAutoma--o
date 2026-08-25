from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from modules.fleet.application.dto import (
    ActorDTO,
    AgentInstanceDTO,
    AgentPoolDTO,
    InteractiveSessionDTO,
    ResourceSnapshotDTO,
)
from modules.fleet.application.ports import (
    AgentConfigurationRepository,
    AgentConnectionRepository,
    AgentInstanceRepository,
    AgentPoolRepository,
    AgentRepository,
    AgentResourceSnapshotRepository,
    FleetOutbox,
    InteractiveSessionRepository,
    TransactionManager,
)
from modules.fleet.application.use_cases._shared import (
    apply_agent_update,
    audit,
    calculate_pool,
    ensure_configuration,
    new_id,
    occupancy_from_pools,
    outbox,
    parse_datetime,
    utcnow,
)
from modules.fleet.domain.errors import AgentDisabledError, AgentNotFoundError, InvalidAgentInstanceError
from modules.fleet.domain.states import DEFAULT_AGENT_POOLS, PresencePolicy
from modules.fleet.domain.value_objects import generate_agent_instance_id
from modules.governance.application.ports import AuditEventRepository


class GetAgent:
    def __init__(self, agents: AgentRepository) -> None:
        self.agents = agents

    def execute(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        return agent


class GetAgentInstances:
    def __init__(self, instances: AgentInstanceRepository) -> None:
        self.instances = instances

    def execute(self, agent_id: str) -> list[AgentInstanceDTO]:
        return self.instances.list_for_agent(agent_id)


class GetAgentHistory:
    def __init__(self, instances: AgentInstanceRepository) -> None:
        self.instances = instances

    def execute(self, agent_id: str) -> dict[str, Any]:
        return {"instances": self.instances.list_for_agent(agent_id)}


class StartAgentInstance:
    def __init__(self, agents: AgentRepository, instances: AgentInstanceRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.instances = instances
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_version: str | None, process_started_at: Any = None, actor: ActorDTO | None = None) -> AgentInstanceDTO:
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        if not agent.enabled or agent.administrative_status == "disabled":
            raise AgentDisabledError("Agent is disabled.")
        now = utcnow()
        self.instances.disconnect_active_for_agent(agent_id, now, "replaced_by_new_instance")
        instance = AgentInstanceDTO(
            id=generate_agent_instance_id(),
            agent_id=agent_id,
            process_started_at=parse_datetime(process_started_at, now),
            connected_at=None,
            last_seen_at=None,
            disconnected_at=None,
            shutdown_reason=None,
            agent_version=agent_version,
            negotiated_protocol_version=None,
            connection_id=None,
            created_at=now,
        )
        created = self.instances.add(instance)
        audit(self.audit, actor or ActorDTO("agent", agent_id), "agent.instance.started", "agent_instance", created.id, after={"agent_id": agent_id})
        outbox(self.outbox, "agent.instance.started", agent_id, {"agent_id": agent_id, "agent_instance_id": created.id})
        self.transaction.commit()
        return created


class CloseAgentInstance:
    def __init__(self, instances: AgentInstanceRepository, transaction: TransactionManager) -> None:
        self.instances = instances
        self.transaction = transaction

    def execute(self, agent_instance_id: str, reason: str | None = None) -> AgentInstanceDTO:
        instance = self.instances.get(agent_instance_id)
        if instance is None:
            raise InvalidAgentInstanceError("AgentInstance not found.")
        updated = self.instances.save(replace(instance, disconnected_at=utcnow(), shutdown_reason=reason))
        self.transaction.commit()
        return updated


class RecordAgentConnected:
    def __init__(
        self,
        agents: AgentRepository,
        instances: AgentInstanceRepository,
        connections: AgentConnectionRepository,
        configurations: AgentConfigurationRepository,
        audit_repo: AuditEventRepository | None,
        outbox_repo: FleetOutbox | None,
        transaction: TransactionManager,
    ) -> None:
        self.agents = agents
        self.instances = instances
        self.connections = connections
        self.configurations = configurations
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, connection_id: str, protocol_version: str, agent_version: str | None, actor: ActorDTO | None = None) -> tuple[AgentInstanceDTO, dict[str, Any]]:
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        if not agent.enabled or agent.administrative_status == "disabled":
            raise AgentDisabledError("Agent is disabled.")
        now = utcnow()
        instance = self.instances.get(agent_instance_id)
        if instance is None:
            instance = self.instances.add(
                AgentInstanceDTO(
                    id=agent_instance_id,
                    agent_id=agent_id,
                    process_started_at=now,
                    connected_at=None,
                    last_seen_at=None,
                    disconnected_at=None,
                    shutdown_reason=None,
                    agent_version=agent_version,
                    negotiated_protocol_version=None,
                    connection_id=None,
                    created_at=now,
                )
            )
        if instance.agent_id != agent_id:
            raise InvalidAgentInstanceError("AgentInstance belongs to another Agent.")
        self.connections.close_active_for_agent(agent_id, now, "replaced_by_new_connection")
        self.connections.open(connection_id, agent_id, agent_instance_id, now, protocol_version)
        updated_instance = self.instances.save(
            replace(
                instance,
                connected_at=now,
                last_seen_at=now,
                disconnected_at=None,
                shutdown_reason=None,
                connection_id=connection_id,
                negotiated_protocol_version=protocol_version,
                agent_version=agent_version or instance.agent_version,
            )
        )
        self.agents.save(apply_agent_update(agent, connectivity_status="online", protocol_version=protocol_version, current_version=agent_version or agent.current_version, last_seen_at=now))
        configuration = ensure_configuration(self.configurations, agent_id)
        audit(self.audit, actor or ActorDTO("agent", agent_id), "agent.connected", "agent", agent_id, metadata={"agent_instance_id": agent_instance_id, "connection_id": connection_id})
        outbox(self.outbox, "agent.connected", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id, "connection_id": connection_id})
        self.transaction.commit()
        return updated_instance, {
            "selected_protocol_version": protocol_version,
            "heartbeat_interval_seconds": configuration.heartbeat_interval_seconds,
            "stale_after_seconds": configuration.stale_after_seconds,
            "offline_after_seconds": configuration.offline_after_seconds,
            "portal_time": now.isoformat(),
            "desired_agent_version": configuration.desired_version,
        }


class RecordAgentDisconnected:
    def __init__(self, agents: AgentRepository, instances: AgentInstanceRepository, connections: AgentConnectionRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.instances = instances
        self.connections = connections
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, connection_id: str | None, reason: str | None = None) -> None:
        now = utcnow()
        agent = self.agents.get(agent_id)
        instance = self.instances.get(agent_instance_id)
        if connection_id:
            self.connections.close(connection_id, now, reason)
        if instance is not None:
            self.instances.save(replace(instance, disconnected_at=now, shutdown_reason=reason, last_seen_at=now))
        if agent is not None:
            self.agents.save(apply_agent_update(agent, connectivity_status="disconnected", last_seen_at=now))
        audit(self.audit, ActorDTO("agent", agent_id), "agent.disconnected", "agent", agent_id, metadata={"agent_instance_id": agent_instance_id, "reason": reason})
        outbox(self.outbox, "agent.disconnected", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id})
        self.transaction.commit()


class RecordAgentHeartbeat:
    def __init__(
        self,
        agents: AgentRepository,
        instances: AgentInstanceRepository,
        snapshots: AgentResourceSnapshotRepository,
        sessions: InteractiveSessionRepository,
        pools: AgentPoolRepository,
        configurations: AgentConfigurationRepository,
        outbox_repo: FleetOutbox | None,
        transaction: TransactionManager,
    ) -> None:
        self.agents = agents
        self.instances = instances
        self.snapshots = snapshots
        self.sessions = sessions
        self.pools = pools
        self.configurations = configurations
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        agent = self.agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        current = self.instances.get_current(agent_id)
        if current is None or current.id != agent_instance_id:
            raise InvalidAgentInstanceError("Heartbeat was not sent by the current AgentInstance.")
        now = utcnow()
        observed_at = parse_datetime(payload.get("observed_at"), now)
        current = self.instances.save(replace(current, last_seen_at=now))

        resources = payload.get("resources") or {}
        snapshot = None
        if isinstance(resources, dict) and resources:
            snapshot = self.snapshots.add(
                ResourceSnapshotDTO(
                    id=new_id("ars"),
                    agent_id=agent_id,
                    agent_instance_id=agent_instance_id,
                    observed_at=observed_at,
                    cpu_usage_percentage=_float_or_none(resources.get("cpu_usage_percentage", resources.get("cpu_percentage"))),
                    memory_total_mb=_int_or_none(resources.get("memory_total_mb")),
                    memory_available_mb=_int_or_none(resources.get("memory_available_mb")),
                    memory_usage_percentage=_float_or_none(resources.get("memory_usage_percentage", resources.get("memory_percentage"))),
                    disk_free_mb=_int_or_none(resources.get("disk_free_mb")),
                    disk_usage_percentage=_float_or_none(resources.get("disk_usage_percentage", resources.get("disk_percentage"))),
                    process_count=_int_or_none(resources.get("process_count")),
                    uptime_seconds=_int_or_none(resources.get("uptime_seconds", payload.get("uptime_seconds"))),
                    revision=1,
                    expires_at=now + timedelta(minutes=10),
                )
            )

        interactive = payload.get("interactive_session") or {}
        if isinstance(interactive, dict) and interactive:
            session = InteractiveSessionDTO(
                agent_id=agent_id,
                agent_instance_id=agent_instance_id,
                available=_bool_or_none(interactive.get("available")),
                locked=_bool_or_none(interactive.get("locked")),
                user=interactive.get("user"),
                session_id=str(interactive.get("session_id")) if interactive.get("session_id") is not None else None,
                session_type=interactive.get("session_type"),
                observed_at=observed_at,
                expires_at=now + timedelta(minutes=10),
            )
            self.sessions.add(replace(session, state=_interactive_state(session.available, session.locked)))

        configuration = ensure_configuration(self.configurations, agent_id)
        pool_payload = payload.get("pools") or payload.get("capacity") or {}
        updated_pools: list[AgentPoolDTO] = []
        if isinstance(pool_payload, dict) and pool_payload:
            for pool_type in DEFAULT_AGENT_POOLS:
                details = pool_payload.get(pool_type) or {}
                if isinstance(details, dict):
                    updated_pools.append(calculate_pool(agent_id, pool_type, observed_at, details, configuration, 1))
            if updated_pools:
                self.pools.replace_current(agent_id, updated_pools)
        else:
            updated_pools = self.pools.list_current(agent_id)

        health = payload.get("health") if payload.get("health") in {"healthy", "degraded", "error"} else agent.health_status
        self.agents.save(
            apply_agent_update(
                agent,
                connectivity_status="online",
                health_status=health,
                occupancy_status=occupancy_from_pools(updated_pools),
                current_version=payload.get("agent_version") or agent.current_version,
                last_seen_at=now,
            )
        )
        outbox(self.outbox, "agent.heartbeat", agent_id, {"agent_id": agent_id, "agent_instance_id": agent_instance_id, "observed_at": observed_at.isoformat()})
        self.transaction.commit()
        return {"ok": True, "server_time": now.isoformat(), "snapshot_id": snapshot.id if snapshot else None}


class DetectStaleAgents:
    def __init__(self, agents: AgentRepository, configurations: AgentConfigurationRepository, transaction: TransactionManager) -> None:
        self.agents = agents
        self.configurations = configurations
        self.transaction = transaction

    def execute(self) -> dict[str, int]:
        now = utcnow()
        counts = {"stale": 0, "offline": 0}
        for agent in self.agents.list():
            config = self.configurations.get(agent.id)
            policy = PresencePolicy(
                heartbeat_interval_seconds=config.heartbeat_interval_seconds if config else 30,
                stale_after_seconds=config.stale_after_seconds if config else 90,
                offline_after_seconds=config.offline_after_seconds if config else 180,
            )
            next_status = policy.connectivity_for(agent.last_seen_at, now)
            if next_status.value != agent.connectivity_status:
                self.agents.save(apply_agent_update(agent, connectivity_status=next_status.value))
                if next_status.value in counts:
                    counts[next_status.value] += 1
        self.transaction.commit()
        return counts


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "sim"}
    return bool(value)


def _interactive_state(available: bool | None, locked: bool | None) -> str:
    if available is None:
        return "unknown"
    if not available:
        return "unavailable"
    return "available_locked" if locked else "available_unlocked"
