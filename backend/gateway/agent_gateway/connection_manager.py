from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import WebSocket


@dataclass
class GatewayConnection:
    agent_id: str
    agent_instance_id: str
    connection_id: str
    websocket: WebSocket


class AgentConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, GatewayConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection: GatewayConnection) -> GatewayConnection | None:
        async with self._lock:
            previous = self._connections.get(connection.agent_id)
            self._connections[connection.agent_id] = connection
            return previous

    async def unregister(self, agent_id: str, connection_id: str) -> None:
        async with self._lock:
            current = self._connections.get(agent_id)
            if current and current.connection_id == connection_id:
                self._connections.pop(agent_id, None)

    async def get(self, agent_id: str) -> GatewayConnection | None:
        async with self._lock:
            return self._connections.get(agent_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._connections)


connection_manager = AgentConnectionManager()
