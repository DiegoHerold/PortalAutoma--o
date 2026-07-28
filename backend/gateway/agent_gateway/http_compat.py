from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.agent_gateway.endpoint import connect_agent
from infrastructure.database import SessionLocal
from modules.fleet.application.dto import ActorDTO
from modules.fleet.application.use_cases import (
    RecordAgentCapabilities,
    RecordAgentCapacity,
    RecordAgentConnected,
    RecordAgentHeartbeat,
    RecordAgentMachineProfile,
    RegisterAgent,
    ValidateAgentCredential,
)
from modules.fleet.domain.errors import FleetError
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.fleet.infrastructure.orm.models import FleetWorkerRecord

router = APIRouter()


@router.post("/agents:register")
@router.post("/v1/agents:register")
def register_agent(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    with SessionLocal() as db:
        return AgentHttpCompatibilityGateway(db).register_agent(payload, _extract_bearer_token(authorization))


@router.post("/agents/{agent_id}/heartbeat")
@router.post("/v1/agents/{agent_id}/heartbeat")
def heartbeat(
    agent_id: str,
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    with SessionLocal() as db:
        try:
            return AgentHttpCompatibilityGateway(db).heartbeat(agent_id, _extract_bearer_token(authorization), payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/events:batch")
@router.post("/v1/agents/{agent_id}/events:batch")
def events_batch(
    agent_id: str,
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    with SessionLocal() as db:
        try:
            return AgentHttpCompatibilityGateway(db).record_events(
                agent_id,
                _extract_bearer_token(authorization),
                payload.get("events") or [],
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.websocket("/agents/ws")
@router.websocket("/v1/agents/ws")
async def agent_websocket(websocket: WebSocket) -> None:
    await connect_agent(websocket)


class AgentHttpCompatibilityGateway:
    """HTTP adapter for pre-WebSocket agents backed by the Fleet module."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.adapters = build_fleet_adapters(db)

    def register_agent(self, payload: dict[str, Any], bearer_token: str | None = None) -> dict[str, Any]:
        registration_token = payload.get("registration_token") or bearer_token
        if not registration_token:
            raise ValueError("Registration token is required.")
        result = RegisterAgent(
            self.adapters.agents,
            self.adapters.registration_tokens,
            self.adapters.credentials,
            self.adapters.configurations,
            self.adapters.audit,
            self.adapters.outbox,
            self.adapters.transaction,
        ).execute(registration_token, payload, ActorDTO(actor_type="agent"))
        secret = result.credential.secret
        return {
            "agent_id": result.agent.id,
            "worker_id": result.agent.id,
            "credential_id": result.credential.id,
            "public_identifier": result.credential.public_identifier,
            "credential_secret": secret,
            "device_token": f"{result.credential.public_identifier}:{secret}" if secret else None,
            "heartbeat_seconds": result.heartbeat_interval_seconds,
            "stale_after_seconds": result.stale_after_seconds,
            "offline_after_seconds": result.offline_after_seconds,
            "gateway_websocket_path": "/api/v1/agent-gateway/connect",
        }

    def heartbeat(self, agent_id: str, bearer_token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        agent = self._authenticate(agent_id, bearer_token)
        agent_instance_id = str(payload.get("agent_instance_id") or f"agi_http_{agent.id}")
        current = self.adapters.instances.get(agent_instance_id)
        if current is None or current.disconnected_at is not None:
            RecordAgentConnected(
                self.adapters.agents,
                self.adapters.instances,
                self.adapters.connections,
                self.adapters.configurations,
                self.adapters.audit,
                self.adapters.outbox,
                self.adapters.transaction,
            ).execute(
                agent.id,
                agent_instance_id,
                f"http_{agent_instance_id}",
                payload.get("protocol_version") or "1.0",
                payload.get("agent_version"),
            )
        return RecordAgentHeartbeat(
            self.adapters.agents,
            self.adapters.instances,
            self.adapters.snapshots,
            self.adapters.interactive_sessions,
            self.adapters.pools,
            self.adapters.configurations,
            self.adapters.outbox,
            self.adapters.transaction,
        ).execute(agent.id, agent_instance_id, payload)

    def record_events(self, agent_id: str, bearer_token: str | None, events: list[dict[str, Any]]) -> dict[str, Any]:
        agent = self._authenticate(agent_id, bearer_token)
        synced_ids: list[str] = []
        for event in events:
            message_type = event.get("event_type")
            payload = event.get("payload") or event
            instance_id = str(payload.get("agent_instance_id") or event.get("agent_instance_id") or f"agi_http_{agent.id}")
            if message_type == "agent.profile.updated":
                RecordAgentMachineProfile(self.adapters.agents, self.adapters.profiles, self.adapters.outbox, self.adapters.transaction).execute(agent.id, instance_id, payload)
            elif message_type == "agent.capabilities.updated":
                RecordAgentCapabilities(self.adapters.agents, self.adapters.capabilities, self.adapters.outbox, self.adapters.transaction).execute(agent.id, instance_id, payload)
            elif message_type == "agent.capacity.updated":
                RecordAgentCapacity(self.adapters.agents, self.adapters.pools, self.adapters.configurations, self.adapters.outbox, self.adapters.transaction).execute(agent.id, instance_id, payload)
            else:
                continue
            synced_ids.append(str(event.get("event_id") or event.get("message_id") or message_type))
        return {"ok": True, "synced_event_ids": synced_ids}

    def _authenticate(self, expected_agent_id: str | None, bearer_token: str | None):
        if not bearer_token:
            raise ValueError("Agente nao autorizado.")
        if ":" in bearer_token:
            public_identifier, _, secret = bearer_token.partition(":")
            try:
                agent = ValidateAgentCredential(self.adapters.agents, self.adapters.credentials, self.adapters.transaction).execute(public_identifier, secret)
            except FleetError as exc:
                raise ValueError(str(exc)) from exc
        else:
            worker = self.db.scalar(select(FleetWorkerRecord).where(FleetWorkerRecord.device_token == bearer_token))
            if worker is None or not worker.agent_id:
                raise ValueError("Agente nao autorizado.")
            agent = self.adapters.agents.get(worker.agent_id)
            if agent is None:
                raise ValueError("Agente nao autorizado.")
        if expected_agent_id and agent.id != expected_agent_id:
            raise ValueError("Agente nao autorizado.")
        return agent


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
