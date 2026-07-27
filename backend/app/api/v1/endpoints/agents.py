from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, status

from app.core.database import SessionLocal
from app.services.agent_gateway_service import AgentGatewayService, extract_bearer_token
from gateway.agent_gateway.endpoint import connect_agent

router = APIRouter()


@router.post("/agents:register")
@router.post("/v1/agents:register")
def register_agent(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    with SessionLocal() as db:
        return AgentGatewayService(db).register_agent(payload, extract_bearer_token(authorization))


@router.post("/agents/{agent_id}/heartbeat")
@router.post("/v1/agents/{agent_id}/heartbeat")
def heartbeat(
    agent_id: str,
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    with SessionLocal() as db:
        try:
            return AgentGatewayService(db).heartbeat(agent_id, extract_bearer_token(authorization), payload)
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
            return AgentGatewayService(db).record_events(
                agent_id,
                extract_bearer_token(authorization),
                payload.get("events") or [],
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.websocket("/agents/ws")
@router.websocket("/v1/agents/ws")
async def agent_websocket(websocket: WebSocket) -> None:
    await connect_agent(websocket)
