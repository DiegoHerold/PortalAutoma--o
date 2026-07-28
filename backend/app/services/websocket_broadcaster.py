import asyncio
import json
import redis.asyncio as redis
from typing import Dict, Set
from fastapi import WebSocket

from app.core.config import get_settings


class WebSocketBroadcaster:
    """
    WebSocket broadcaster that supports multi-instance deployment via Redis pub/sub.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._pubsub = None
        self._listening = False

    async def connect(self, websocket: WebSocket, user_id: str):
        """Add a WebSocket connection for a user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Start Redis listener if not already started
        if not self._listening:
            await self._start_redis_listener()

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection for a user."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast a message to all connections for a specific user."""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(connection)
            
            # Clean up disconnected WebSockets
            for conn in disconnected:
                self.active_connections[user_id].discard(conn)

    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.broadcast_to_user(user_id, message)

    async def publish(self, channel: str, message: dict):
        """Publish a message to Redis pub/sub for multi-instance support."""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.settings.redis_url)
        
        await self.redis_client.publish(channel, json.dumps(message))

    async def _start_redis_listener(self):
        """Start Redis pub/sub listener for job updates."""
        if self._listening:
            return
        
        self._listening = True
        
        try:
            self.redis_client = redis.from_url(self.settings.redis_url)
            self._pubsub = self.redis_client.pubsub()
            await self._pubsub.subscribe("job_updates")
            
            # Run listener in background task
            asyncio.create_task(self._listen_for_messages())
        except Exception as e:
            print(f"Failed to start Redis listener: {e}")
            self._listening = False

    async def _listen_for_messages(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
        if not self._pubsub:
            return
        
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self.broadcast_to_all(data)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"Redis listener error: {e}")
        finally:
            self._listening = False

    async def cleanup(self):
        """Cleanup Redis connections."""
        if self._pubsub:
            await self._pubsub.unsubscribe("job_updates")
            await self._pubsub.close()
        if self.redis_client:
            await self.redis_client.close()


# Global broadcaster instance
broadcaster = WebSocketBroadcaster()


def get_broadcaster() -> WebSocketBroadcaster:
    return broadcaster