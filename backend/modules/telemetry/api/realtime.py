from __future__ import annotations

import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from modules.access.infrastructure.authentication import JwtTokenIssuer

router = APIRouter()

PRAZO_AUTENTICACAO_S = 5.0


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.register(websocket, user_id)

    def register(self, websocket: WebSocket, user_id: str) -> None:
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        connections = self.active_connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: dict) -> None:
        disconnected: list[WebSocket] = []
        for connection in self.active_connections.get(user_id, set()):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection, user_id)

    async def broadcast_to_all(self, message: dict) -> None:
        for user_id in list(self.active_connections.keys()):
            await self.broadcast_to_user(user_id, message)


manager = ConnectionManager()


@router.websocket("/executions")
async def websocket_executions(websocket: WebSocket) -> None:
    """O token chega na primeira mensagem (``{"type": "auth", "token": "..."}``), nunca na URL."""
    await websocket.accept()
    try:
        bruto = await asyncio.wait_for(websocket.receive_text(), timeout=PRAZO_AUTENTICACAO_S)
        mensagem = json.loads(bruto)
        if not isinstance(mensagem, dict) or mensagem.get("type") != "auth" or not isinstance(mensagem.get("token"), str):
            raise ValueError("Primeira mensagem precisa ser a autenticação.")
        payload = JwtTokenIssuer().decode_access_token(mensagem["token"])
        user_id = str(payload.get("sub"))
        if not user_id or user_id == "None":
            raise ValueError("Missing token subject.")
    except Exception:  # noqa: BLE001 - qualquer falha de autenticação fecha igual
        await websocket.close(code=4001, reason="Unauthorized")
        return
    manager.register(websocket, user_id)
    await websocket.send_text(json.dumps({"type": "connected", "message": "Real-time connection established"}))
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


def get_connection_manager() -> ConnectionManager:
    return manager
