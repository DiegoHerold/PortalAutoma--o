from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session
import json
from typing import Dict, Set

from app.core.database import get_db
from app.core.security import decode_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected websockets
            for conn in disconnected:
                self.active_connections[user_id].discard(conn)

    async def broadcast_to_all(self, message: dict):
        for user_id in list(self.active_connections.keys()):
            await self.broadcast_to_user(user_id, message)


manager = ConnectionManager()


@router.websocket("/executions")
async def websocket_executions(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time job execution updates.
    
    Authentication via token query parameter.
    Emits job status changes and ETA updates.
    """
    try:
        # Verify JWT token
        payload = decode_token(token)
        user_id = str(payload.get("sub"))
        
        await manager.connect(websocket, user_id)
        
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Real-time connection established"
        }))
        
        # Keep connection alive
        try:
            while True:
                # Wait for ping/pong to keep connection alive
                data = await websocket.receive_text()
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket, user_id)
            
    except Exception as e:
        # Invalid token or other error
        await websocket.close(code=4001, reason="Unauthorized")


# Global manager instance for broadcasting
def get_connection_manager() -> ConnectionManager:
    return manager
