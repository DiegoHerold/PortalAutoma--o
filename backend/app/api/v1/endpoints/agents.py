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
    """
    Dispatch and receive run as two independent loops sharing one connection,
    instead of one strict send-then-block-for-response cycle. That old shape
    meant a worker could only ever run one automation at a time no matter how
    its slots were configured, since claim_next_command() was never even
    called again until the single in-flight command's response came back.
    Now claim_next_command() keeps polling (and pushing new commands) as long
    as the worker has free slots -- which claim_next_command() already checks
    via worker.max_concurrency -- while responses are read and matched back to
    their job/execution independently, as they arrive, possibly out of order.
    """
    token = extract_bearer_token(websocket.headers.get("authorization"))
    with SessionLocal() as db:
        worker = AgentGatewayService(db).authenticate_by_token(token)
        if worker is None:
            await websocket.close(code=1008, reason="Agente nao autorizado")
            return
        worker_id = worker.id

    await websocket.accept()
    send_lock = asyncio.Lock()
    stop_dispatch = asyncio.Event()

    async def dispatch_loop() -> None:
        while not stop_dispatch.is_set():
            with SessionLocal() as db:
                command = AgentGatewayService(db).claim_next_command(worker_id)
            if command is None:
                await asyncio.sleep(2)
                continue
            payload = json.dumps(command.payload, ensure_ascii=False)
            async with send_lock:
                await websocket.send_text(payload)

    dispatch_task = asyncio.create_task(dispatch_loop())
    try:
        while True:
            raw_response = await websocket.receive_text()
            with SessionLocal() as db:
                AgentGatewayService(db).finish_command_from_response(worker_id, raw_response)
    except WebSocketDisconnect:
        with SessionLocal() as db:
            AgentGatewayService(db).mark_all_lost_for_worker(
                worker_id, "Conexao WebSocket do Automation Agent foi encerrada durante a execucao."
            )
    except Exception as exc:
        with SessionLocal() as db:
            AgentGatewayService(db).mark_all_lost_for_worker(worker_id, str(exc))
        await websocket.close(code=1011, reason="Falha no gateway do agente")
    finally:
        stop_dispatch.set()
        dispatch_task.cancel()
        try:
            await dispatch_task
        except (asyncio.CancelledError, Exception):
            pass
