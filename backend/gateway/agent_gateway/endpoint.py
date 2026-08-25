from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, text

from infrastructure.database import SessionLocal
from gateway.agent_gateway.authentication import authenticate_agent
from gateway.agent_gateway.command_delivery import deliver_pending_commands
from gateway.agent_gateway.connection_manager import GatewayConnection, connection_manager
from gateway.agent_gateway.errors import GatewayError, MessageTooLarge
from gateway.agent_gateway.limits import load_gateway_limits
from gateway.agent_gateway.message_router import route_agent_message, validate_envelope
from gateway.agent_gateway.protocol_negotiation import negotiate_protocol
from modules.dispatch.infrastructure.orm.models import AgentCommandRecord
from modules.fleet.application.use_cases import RecordAgentConnected, RecordAgentDisconnected
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.telemetry.infrastructure.orm.models import EventAcknowledgementRecord, ExecutionEventRecord

router = APIRouter()


@router.get("/agent-gateway/health")
async def gateway_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "component": "agent_gateway",
        "connected_agents": await connection_manager.count(),
    }


@router.get("/agent-gateway/readiness")
async def gateway_readiness() -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(text("select 1"))
        pending_commands = int(
            db.scalar(select(func.count(AgentCommandRecord.id)).where(AgentCommandRecord.status.in_(["pending", "sent"])))
            or 0
        )
        telemetry_events = int(db.scalar(select(func.count(ExecutionEventRecord.id))) or 0)
        telemetry_acknowledgements = int(db.scalar(select(func.count(EventAcknowledgementRecord.execution_attempt_id))) or 0)
    return {
        "status": "ready",
        "component": "agent_gateway",
        "checks": {
            "database": "ok",
            "connected_agents": await connection_manager.count(),
            "command_delivery": {"pending_or_sent_commands": pending_commands},
            "telemetry_ingestion": {"events": telemetry_events, "acknowledgements": telemetry_acknowledgements},
        },
    }


@router.websocket("/agent-gateway/connect")
async def connect_agent(websocket: WebSocket) -> None:
    limits = load_gateway_limits()
    connection_id = f"conn_{uuid4().hex}"
    authenticated_agent = None
    agent_instance_id = None
    protocol_version = None
    await websocket.accept()
    try:
        with SessionLocal() as db:
            authenticated_agent = authenticate_agent(db, websocket.headers.get("authorization"))

        handshake = await asyncio.wait_for(websocket.receive_json(), timeout=limits.handshake_timeout_seconds)
        handshake_payload = _handshake_payload(handshake)
        agent_id = str(handshake_payload.get("agent_id") or "")
        agent_instance_id = str(handshake_payload.get("agent_instance_id") or "")
        if agent_id != authenticated_agent.agent.id or not agent_instance_id:
            await _send_error(websocket, "HANDSHAKE_INVALID", "Handshake Agent identity does not match credential.")
            await _safe_close(websocket, code=1008)
            return
        negotiated = negotiate_protocol(handshake_payload.get("supported_protocol_versions") or [])
        protocol_version = negotiated.selected_protocol_version

        with SessionLocal() as db:
            adapters = build_fleet_adapters(db)
            _, connected_payload = RecordAgentConnected(
                adapters.agents,
                adapters.instances,
                adapters.connections,
                adapters.configurations,
                adapters.audit,
                adapters.outbox,
                adapters.transaction,
            ).execute(agent_id, agent_instance_id, connection_id, protocol_version, handshake_payload.get("agent_version"))

        previous = await connection_manager.register(GatewayConnection(agent_id, agent_instance_id, connection_id, websocket))
        if previous is not None:
            await _close_previous(previous)

        await websocket.send_json(
            _portal_envelope(
                "agent.connected",
                connected_payload,
                protocol_version,
                agent_id=agent_id,
                agent_instance_id=agent_instance_id,
            )
        )

        delivery_task = asyncio.create_task(_delivery_loop(websocket, agent_id, agent_instance_id, protocol_version, limits))
        try:
            while True:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=limits.idle_timeout_seconds)
                if len(raw.encode("utf-8")) > limits.max_message_bytes:
                    raise MessageTooLarge("Message is too large.")
                envelope = json.loads(raw)
                validate_envelope(envelope, agent_id, agent_instance_id, protocol_version, limits)
                with SessionLocal() as db:
                    response = route_agent_message(db, envelope, protocol_version, limits)
                await websocket.send_json(
                    _portal_envelope(
                        "portal.ack",
                        response,
                        protocol_version,
                        agent_id=agent_id,
                        agent_instance_id=agent_instance_id,
                        correlation_id=envelope.get("message_id"),
                    )
                )
        finally:
            delivery_task.cancel()
            try:
                await delivery_task
            except asyncio.CancelledError:
                pass
    except WebSocketDisconnect:
        pass
    except GatewayError as exc:
        await _send_error(
            websocket,
            exc.code,
            str(exc),
            protocol_version=protocol_version or "1.0",
            agent_id=authenticated_agent.agent.id if authenticated_agent else None,
            agent_instance_id=agent_instance_id,
        )
        await _safe_close(websocket, code=1008)
    except Exception as exc:
        await _send_error(
            websocket,
            "GATEWAY_INTERNAL_ERROR",
            "Gateway failed while processing the connection.",
            protocol_version=protocol_version or "1.0",
            agent_id=authenticated_agent.agent.id if authenticated_agent else None,
            agent_instance_id=agent_instance_id,
        )
        await _safe_close(websocket, code=1011)
    finally:
        if authenticated_agent and agent_instance_id:
            await connection_manager.unregister(authenticated_agent.agent.id, connection_id)
            with SessionLocal() as db:
                adapters = build_fleet_adapters(db)
                RecordAgentDisconnected(adapters.agents, adapters.instances, adapters.connections, adapters.audit, adapters.outbox, adapters.transaction).execute(
                    authenticated_agent.agent.id,
                    agent_instance_id,
                    connection_id,
                    "websocket_closed",
                )


async def _delivery_loop(websocket: WebSocket, agent_id: str, agent_instance_id: str, protocol_version: str, limits) -> None:
    while True:
        with SessionLocal() as db:
            await deliver_pending_commands(db, websocket, agent_id, agent_instance_id, protocol_version, limits)
        await asyncio.sleep(2)


def _handshake_payload(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("message_type") == "agent.connect":
        return message.get("payload") or {}
    return message


def _portal_envelope(
    message_type: str,
    payload: dict[str, Any],
    protocol_version: str = "1.0",
    *,
    agent_id: str | None = None,
    agent_instance_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    envelope = {
        "protocol_version": protocol_version,
        "message_id": f"msg_{uuid4().hex}",
        "message_type": message_type,
        "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
    if agent_id:
        envelope["agent_id"] = agent_id
    if agent_instance_id:
        envelope["agent_instance_id"] = agent_instance_id
    if correlation_id:
        envelope["correlation_id"] = correlation_id
    return envelope


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    *,
    protocol_version: str = "1.0",
    agent_id: str | None = None,
    agent_instance_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    try:
        await websocket.send_json(
            _portal_envelope(
                "portal.error",
                {"code": code, "message": message},
                protocol_version,
                agent_id=agent_id,
                agent_instance_id=agent_instance_id,
                correlation_id=correlation_id,
            )
        )
    except Exception:
        pass


async def _safe_close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        pass


async def _close_previous(connection: GatewayConnection) -> None:
    try:
        await connection.websocket.send_json(
            _portal_envelope(
                "portal.disconnect",
                {"reason": "replaced_by_new_connection"},
                agent_id=connection.agent_id,
                agent_instance_id=connection.agent_instance_id,
            )
        )
        await connection.websocket.close(code=4000)
    except Exception:
        pass
