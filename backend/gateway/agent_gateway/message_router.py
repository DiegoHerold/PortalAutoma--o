from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from gateway.agent_gateway.errors import EnvelopeValidationFailed, MessageTooLarge, MessageTypeUnsupported
from gateway.agent_gateway.limits import GatewayLimits
from modules.fleet.application.dto import AgentDiagnosticDTO
from modules.fleet.application.use_cases import (
    AcknowledgeAgentCommand,
    RecordAgentCapabilities,
    RecordAgentCapacity,
    RecordAgentHeartbeat,
    RecordAgentMachineProfile,
)
from modules.fleet.application.use_cases._shared import apply_agent_update, new_id, utcnow
from modules.fleet.domain.errors import FleetError
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.telemetry.infrastructure.repositories.sqlalchemy_inbox import InboxPayloadConflictError


SUPPORTED_AGENT_MESSAGES = {
    "agent.connected",
    "agent.resumed",
    "agent.heartbeat",
    "agent.profile.updated",
    "agent.capacity.updated",
    "agent.capabilities.updated",
    "agent.diagnostic.result",
    "agent.update.progress",
    "agent.command.ack",
}

DEFERRED_EXECUTION_MESSAGES = {
    "execution.accepted",
    "execution.rejected",
    "execution.started",
    "execution.event.batch",
    "execution.completed",
    "execution.failed",
    "execution.cancelled",
    "execution.timed_out",
    "execution.recovered",
    "artifact.created",
    "artifact.uploaded",
    "artifact.failed",
}


def validate_envelope(envelope: dict[str, Any], authenticated_agent_id: str, agent_instance_id: str, protocol_version: str, limits: GatewayLimits) -> None:
    required = ["protocol_version", "message_id", "message_type", "sent_at", "agent_id", "agent_instance_id", "payload"]
    missing = [field for field in required if field not in envelope]
    if missing:
        raise EnvelopeValidationFailed(f"Envelope is missing fields: {', '.join(missing)}.")
    if envelope["protocol_version"] != protocol_version:
        raise EnvelopeValidationFailed("Envelope protocol version differs from negotiated protocol.")
    if envelope["agent_id"] != authenticated_agent_id:
        raise EnvelopeValidationFailed("Agent cannot send messages for another Agent.")
    if envelope["agent_instance_id"] != agent_instance_id:
        raise EnvelopeValidationFailed("Message AgentInstance differs from the active connection.")
    if not isinstance(envelope.get("payload"), dict):
        raise EnvelopeValidationFailed("Envelope payload must be an object.")
    sent_at = _parse_sent_at(envelope.get("sent_at"))
    if abs((datetime.utcnow() - sent_at).total_seconds()) > 300:
        raise EnvelopeValidationFailed("Envelope timestamp is outside the accepted replay window.")
    if envelope["message_type"] == "agent.heartbeat" and _rough_size(envelope["payload"]) > limits.max_heartbeat_payload_bytes:
        raise MessageTooLarge("Heartbeat payload is too large.")
    if envelope["message_type"] == "agent.capabilities.updated":
        capabilities = envelope["payload"].get("capabilities") or []
        if len(capabilities) > limits.max_capabilities_per_message:
            raise MessageTooLarge("Capabilities payload has too many items.")


def route_agent_message(db: Session, envelope: dict[str, Any], protocol_version: str, limits: GatewayLimits) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    agent_id = envelope["agent_id"]
    agent_instance_id = envelope["agent_instance_id"]
    message_type = envelope["message_type"]
    payload = envelope["payload"]

    if message_type in DEFERRED_EXECUTION_MESSAGES or message_type not in SUPPORTED_AGENT_MESSAGES:
        raise MessageTypeUnsupported("MESSAGE_TYPE_NOT_SUPPORTED")

    try:
        is_new = adapters.inbox.record_once(envelope["message_id"], "agent", agent_id, message_type, envelope)
    except InboxPayloadConflictError as exc:
        raise EnvelopeValidationFailed(str(exc)) from exc
    if not is_new:
        adapters.transaction.commit()
        return {"ok": True, "duplicate": True, "message_id": envelope["message_id"]}

    try:
        if message_type == "agent.heartbeat":
            result = RecordAgentHeartbeat(adapters.agents, adapters.instances, adapters.snapshots, adapters.interactive_sessions, adapters.pools, adapters.configurations, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.profile.updated":
            result = RecordAgentMachineProfile(adapters.agents, adapters.profiles, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.capabilities.updated":
            result = RecordAgentCapabilities(adapters.agents, adapters.capabilities, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.capacity.updated":
            result = RecordAgentCapacity(adapters.agents, adapters.pools, adapters.configurations, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.command.ack":
            result = AcknowledgeAgentCommand(adapters.commands, adapters.outbox, adapters.transaction).execute(agent_id, payload)
        elif message_type == "agent.diagnostic.result":
            result = _record_diagnostic_result(adapters, agent_id, agent_instance_id, payload)
        elif message_type == "agent.update.progress":
            result = _record_update_progress(adapters, agent_id, payload)
        elif message_type in {"agent.connected", "agent.resumed"}:
            result = {"ok": True, "pending_commands": [item.id for item in adapters.commands.pending_for_agent(agent_id, limits.max_pending_commands_per_agent)]}
            adapters.transaction.commit()
        else:
            raise MessageTypeUnsupported("MESSAGE_TYPE_NOT_SUPPORTED")
        adapters.inbox.mark_processed(envelope["message_id"])
        adapters.transaction.commit()
        return {"ok": True, "message_id": envelope["message_id"], "message_type": message_type, "result": _json(result)}
    except FleetError:
        adapters.transaction.rollback()
        raise


def _record_diagnostic_result(adapters, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    diagnostic = AgentDiagnosticDTO(
        id=new_id("adg"),
        agent_id=agent_id,
        agent_instance_id=agent_instance_id,
        request_command_id=payload.get("request_command_id") or payload.get("command_id"),
        status=str(payload.get("status") or "completed"),
        summary=payload.get("summary"),
        details=payload.get("details") or {},
        artifact_id=payload.get("artifact_id"),
        requested_at=utcnow(),
        completed_at=utcnow(),
        error=payload.get("error"),
    )
    saved = adapters.diagnostics.add(diagnostic)
    adapters.outbox.append_event("agent.diagnostic.result", agent_id, {"agent_id": agent_id, "diagnostic_id": saved.id})
    return {"diagnostic_id": saved.id, "status": saved.status}


def _record_update_progress(adapters, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    agent = adapters.agents.get(agent_id)
    if agent is None:
        return {"ok": False}
    status = str(payload.get("status") or "")
    current_version = payload.get("current_version") or agent.current_version
    administrative_status = "enabled" if status in {"completed", "succeeded"} else agent.administrative_status
    adapters.agents.save(apply_agent_update(agent, current_version=current_version, administrative_status=administrative_status))
    adapters.outbox.append_event("agent.update.progress", agent_id, {"agent_id": agent_id, "status": status, "progress": payload.get("progress")})
    return {"ok": True, "status": status}


def _parse_sent_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise EnvelopeValidationFailed("Envelope sent_at must be a date-time string.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise EnvelopeValidationFailed("Envelope sent_at is invalid.") from exc


def _rough_size(payload: dict[str, Any]) -> int:
    return len(str(payload).encode("utf-8"))


def _json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
