from __future__ import annotations

from dataclasses import replace
from typing import Any

from modules.fleet.application.dto import ActorDTO, AgentConfigurationDTO
from modules.fleet.application.ports import (
    AgentCommandRepository,
    AgentConfigurationRepository,
    AgentRepository,
    FleetOutbox,
    TransactionManager,
)
from modules.fleet.application.use_cases._shared import apply_agent_update, audit, default_configuration, outbox, utcnow
from modules.fleet.domain.errors import AgentNotFoundError, InvalidAgentStateTransition
from modules.governance.application.ports import AuditEventRepository


class ListAgents:
    def __init__(self, agents: AgentRepository) -> None:
        self.agents = agents

    def execute(self) -> list:
        return self.agents.list()


class EnableAgent:
    def __init__(self, agents: AgentRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO):
        agent = _get(self.agents, agent_id)
        updated = self.agents.save(apply_agent_update(agent, enabled=True, administrative_status="enabled", disabled_at=None))
        audit(self.audit, actor, "agent.enabled", "agent", agent_id)
        outbox(self.outbox, "agent.enabled", agent_id, {"agent_id": agent_id})
        self.transaction.commit()
        return updated


class DisableAgent:
    def __init__(self, agents: AgentRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO, reason: str | None = None):
        agent = _get(self.agents, agent_id)
        updated = self.agents.save(apply_agent_update(agent, enabled=False, administrative_status="disabled", connectivity_status="offline", disabled_at=utcnow()))
        audit(self.audit, actor, "agent.disabled", "agent", agent_id, metadata={"reason": reason})
        outbox(self.outbox, "agent.disabled", agent_id, {"agent_id": agent_id})
        self.transaction.commit()
        return updated


class DrainAgent:
    def __init__(self, agents: AgentRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO):
        agent = _get(self.agents, agent_id)
        if agent.administrative_status == "disabled":
            raise InvalidAgentStateTransition("Disabled agents cannot drain.")
        updated = self.agents.save(apply_agent_update(agent, administrative_status="draining"))
        audit(self.audit, actor, "agent.draining", "agent", agent_id)
        outbox(self.outbox, "agent.draining", agent_id, {"agent_id": agent_id})
        self.transaction.commit()
        return updated


class ResumeAgent:
    def __init__(self, agents: AgentRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO):
        agent = _get(self.agents, agent_id)
        if agent.administrative_status == "disabled":
            raise InvalidAgentStateTransition("Disabled agents must be explicitly enabled.")
        updated = self.agents.save(apply_agent_update(agent, administrative_status="enabled"))
        audit(self.audit, actor, "agent.resumed", "agent", agent_id)
        outbox(self.outbox, "agent.resumed", agent_id, {"agent_id": agent_id})
        self.transaction.commit()
        return updated


class SetAgentMaintenance:
    def __init__(self, agents: AgentRepository, configurations: AgentConfigurationRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.configurations = configurations
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO, enabled: bool = True):
        agent = _get(self.agents, agent_id)
        if agent.administrative_status == "disabled":
            raise InvalidAgentStateTransition("Disabled agents cannot enter maintenance.")
        config = self.configurations.get(agent_id) or default_configuration(agent_id)
        self.configurations.save(replace(config, maintenance=enabled, updated_at=utcnow()))
        status = "maintenance" if enabled else "enabled"
        updated = self.agents.save(apply_agent_update(agent, administrative_status=status))
        audit(self.audit, actor, "agent.maintenance_enabled" if enabled else "agent.maintenance_disabled", "agent", agent_id)
        outbox(self.outbox, "agent.maintenance.updated", agent_id, {"agent_id": agent_id, "maintenance": enabled})
        self.transaction.commit()
        return updated


class UpdateAgentConfiguration:
    def __init__(
        self,
        agents: AgentRepository,
        configurations: AgentConfigurationRepository,
        commands: AgentCommandRepository,
        audit_repo: AuditEventRepository | None,
        outbox_repo: FleetOutbox | None,
        transaction: TransactionManager,
    ) -> None:
        self.agents = agents
        self.configurations = configurations
        self.commands = commands
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO, payload: dict[str, Any]) -> dict[str, Any]:
        agent = _get(self.agents, agent_id)
        current = self.configurations.get(agent_id) or default_configuration(agent_id)
        updated = AgentConfigurationDTO(
            agent_id=agent_id,
            heartbeat_interval_seconds=int(payload.get("heartbeat_interval_seconds") or current.heartbeat_interval_seconds),
            stale_after_seconds=int(payload.get("stale_after_seconds") or current.stale_after_seconds),
            offline_after_seconds=int(payload.get("offline_after_seconds") or current.offline_after_seconds),
            administrator_pool_limits=payload.get("administrator_pool_limits") or current.administrator_pool_limits,
            enabled_pools=payload.get("enabled_pools") or current.enabled_pools,
            allowlist_capabilities=payload.get("allowlist_capabilities") or current.allowlist_capabilities,
            maintenance=bool(payload.get("maintenance", current.maintenance)),
            desired_version=payload.get("desired_version", current.desired_version),
            restrictions=payload.get("restrictions") or current.restrictions,
            updated_at=utcnow(),
        )
        saved = self.configurations.save(updated)
        if saved.desired_version != agent.desired_version:
            self.agents.save(apply_agent_update(agent, desired_version=saved.desired_version))
        command = self.commands.create(agent_id, "agent.configuration.update", {"configuration": _config_payload(saved)})
        audit(self.audit, actor, "agent.configuration_updated", "agent", agent_id, after=_config_payload(saved))
        outbox(self.outbox, "agent.configuration.updated", agent_id, {"agent_id": agent_id, "command_id": command.id})
        self.transaction.commit()
        return {"configuration": saved, "command": command}


def _get(agents: AgentRepository, agent_id: str):
    agent = agents.get(agent_id)
    if agent is None:
        raise AgentNotFoundError("Agent not found.")
    return agent


def _config_payload(config: AgentConfigurationDTO) -> dict[str, Any]:
    return {
        "heartbeat_interval_seconds": config.heartbeat_interval_seconds,
        "stale_after_seconds": config.stale_after_seconds,
        "offline_after_seconds": config.offline_after_seconds,
        "administrator_pool_limits": config.administrator_pool_limits,
        "enabled_pools": config.enabled_pools,
        "allowlist_capabilities": config.allowlist_capabilities,
        "maintenance": config.maintenance,
        "desired_version": config.desired_version,
        "restrictions": config.restrictions,
    }
