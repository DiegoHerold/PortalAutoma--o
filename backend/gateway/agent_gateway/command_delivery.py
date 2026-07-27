from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from sqlalchemy.orm import Session

from gateway.agent_gateway.limits import GatewayLimits
from modules.fleet.infrastructure.adapters import build_fleet_adapters


def build_command_envelope(agent_id: str, agent_instance_id: str, protocol_version: str, command) -> dict[str, Any]:
    payload = {
        "command_id": command.id,
        "command_sequence": command.command_sequence,
        **(command.payload or {}),
    }
    return {
        "protocol_version": protocol_version,
        "message_id": f"msg_{uuid4().hex}",
        "message_type": command.message_type,
        "sent_at": datetime.utcnow().isoformat(),
        "agent_id": agent_id,
        "agent_instance_id": agent_instance_id,
        "correlation_id": command.id,
        "causation_id": None,
        "payload": payload,
    }


async def deliver_pending_commands(db: Session, websocket: WebSocket, agent_id: str, agent_instance_id: str, protocol_version: str, limits: GatewayLimits) -> list[str]:
    adapters = build_fleet_adapters(db)
    delivered: list[str] = []
    for command in adapters.commands.pending_for_agent(agent_id, limits.max_pending_commands_per_agent):
        envelope = build_command_envelope(agent_id, agent_instance_id, protocol_version, command)
        await websocket.send_json(envelope)
        adapters.commands.mark_sent(command.id, agent_instance_id, datetime.utcnow())
        delivered.append(command.id)
    adapters.transaction.commit()
    return delivered
