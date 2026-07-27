from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from modules.fleet.application.dto import ActorDTO, AgentDiagnosticDTO
from modules.fleet.application.ports import AgentCommandRepository, AgentDiagnosticRepository, AgentRepository, FleetOutbox, TransactionManager
from modules.fleet.application.use_cases._shared import apply_agent_update, audit, new_id, outbox, utcnow
from modules.fleet.domain.errors import AgentNotFoundError
from modules.governance.application.ports import AuditEventRepository


class RequestAgentDiagnostic:
    def __init__(self, agents: AgentRepository, commands: AgentCommandRepository, diagnostics: AgentDiagnosticRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.commands = commands
        self.diagnostics = diagnostics
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _require_agent(self.agents, agent_id)
        command = self.commands.create(agent_id, "agent.diagnostic.request", payload or {}, expires_at=utcnow() + timedelta(hours=1))
        diagnostic = self.diagnostics.add(
            AgentDiagnosticDTO(
                id=new_id("adg"),
                agent_id=agent_id,
                agent_instance_id=None,
                request_command_id=command.id,
                status="requested",
                requested_at=utcnow(),
            )
        )
        audit(self.audit, actor, "agent.diagnostic_requested", "agent", agent_id, after={"command_id": command.id, "diagnostic_id": diagnostic.id})
        outbox(self.outbox, "agent.diagnostic_requested", agent_id, {"agent_id": agent_id, "command_id": command.id})
        self.transaction.commit()
        return {"status": "pending_delivery", "command": command, "diagnostic": diagnostic}


class RequestAgentCapabilitiesRefresh:
    def __init__(self, agents: AgentRepository, commands: AgentCommandRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.commands = commands
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO) -> dict[str, Any]:
        _require_agent(self.agents, agent_id)
        command = self.commands.create(agent_id, "agent.capabilities.request", {}, expires_at=utcnow() + timedelta(hours=1))
        audit(self.audit, actor, "agent.capabilities_requested", "agent", agent_id, after={"command_id": command.id})
        outbox(self.outbox, "agent.capabilities.requested", agent_id, {"agent_id": agent_id, "command_id": command.id})
        self.transaction.commit()
        return {"status": "pending_delivery", "command": command}


class RequestAgentUpdate:
    def __init__(self, agents: AgentRepository, commands: AgentCommandRepository, audit_repo: AuditEventRepository | None, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.agents = agents
        self.commands = commands
        self.audit = audit_repo
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, actor: ActorDTO, desired_version: str) -> dict[str, Any]:
        agent = _require_agent(self.agents, agent_id)
        self.agents.save(apply_agent_update(agent, desired_version=desired_version, administrative_status="updating"))
        command = self.commands.create(agent_id, "agent.update.request", {"desired_version": desired_version}, expires_at=utcnow() + timedelta(hours=6))
        audit(self.audit, actor, "agent.update_requested", "agent", agent_id, after={"desired_version": desired_version, "command_id": command.id})
        outbox(self.outbox, "agent.update.requested", agent_id, {"agent_id": agent_id, "command_id": command.id})
        self.transaction.commit()
        return {"status": "pending_delivery", "command": command}


class AcknowledgeAgentCommand:
    def __init__(self, commands: AgentCommandRepository, outbox_repo: FleetOutbox | None, transaction: TransactionManager) -> None:
        self.commands = commands
        self.outbox = outbox_repo
        self.transaction = transaction

    def execute(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        command_id = str(payload.get("command_id") or "")
        sequence = payload.get("command_sequence")
        status = str(payload.get("status") or "received")
        acknowledged = self.commands.acknowledge(agent_id, command_id, int(sequence) if sequence is not None else None, status, utcnow())
        outbox(self.outbox, "agent.command.acknowledged", agent_id, {"agent_id": agent_id, "command_id": command_id, "status": status})
        self.transaction.commit()
        return {"ok": acknowledged is not None, "command_id": command_id, "status": status}


def _require_agent(agents: AgentRepository, agent_id: str):
    agent = agents.get(agent_id)
    if agent is None:
        raise AgentNotFoundError("Agent not found.")
    return agent
