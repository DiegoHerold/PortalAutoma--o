from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.database import SessionLocal, get_db
from app.services.agent_gateway_service import AgentGatewayService, extract_bearer_token

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
    token = extract_bearer_token(websocket.headers.get("authorization"))
    with SessionLocal() as db:
        worker = AgentGatewayService(db).authenticate_by_token(token)
        if worker is None:
            await websocket.close(code=1008, reason="Agente nao autorizado")
            return
        worker_id = worker.id

    await websocket.accept()
    active_command: tuple[int, int] | None = None
    try:
        while True:
            with SessionLocal() as db:
                command = AgentGatewayService(db).claim_next_command(worker_id)
            if command is None:
                await asyncio.sleep(2)
                continue

            active_command = (command.job_id, command.execution_id)
            await websocket.send_text(json.dumps(command.payload, ensure_ascii=False))
            raw_response = await websocket.receive_text()
            with SessionLocal() as db:
                AgentGatewayService(db).finish_command(worker_id, command.job_id, command.execution_id, raw_response)
            active_command = None
    except WebSocketDisconnect:
        if active_command is not None:
            with SessionLocal() as db:
                AgentGatewayService(db).mark_lost(
                    worker_id,
                    active_command[0],
                    active_command[1],
                    "Conexao WebSocket do Automation Agent foi encerrada durante a execucao.",
                )
    except Exception as exc:
        if active_command is not None:
            with SessionLocal() as db:
                AgentGatewayService(db).mark_lost(worker_id, active_command[0], active_command[1], str(exc))
        await websocket.close(code=1011, reason="Falha no gateway do agente")
