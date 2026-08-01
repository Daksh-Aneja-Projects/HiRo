"""WebSocket connection manager for real-time telemetry fan-out.

This file used to also define an APIRouter with an SSE endpoint and a WebSocket
endpoint. That router was never mounted: server.py builds its route table from
comprehensive_routes.ALL_ROUTERS, whose `streaming_router` is a different object
defined in that module. Only `manager` below was ever reachable (server.py and
comprehensive_routes.py both import it), so the unmounted half is gone.
"""
import logging
from typing import Dict, Any, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.telemetry_subscribers: Set[str] = set()
        logger.info("✓ WebSocket ConnectionManager Initialized.")

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WS Client connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.telemetry_subscribers:
            self.telemetry_subscribers.remove(client_id)
        logger.info(f"WS Client disconnected: {client_id}")

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def subscribe_telemetry(self, client_id: str):
        self.telemetry_subscribers.add(client_id)
        logger.info(f"Client {client_id} subscribed to telemetry.")

    async def broadcast_telemetry(self, telemetry_data: Dict[str, Any]):
        """Broadcasts telemetry data only to subscribed clients."""
        # Frontend clients match on message.type === 'telemetry_metrics' and read message.data.
        message = {"type": "telemetry_metrics", "data": telemetry_data}

        for client_id in list(self.telemetry_subscribers):
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except WebSocketDisconnect:
                    self.disconnect(client_id)
                except Exception as e:
                    logger.error(f"Error broadcasting telemetry to {client_id}: {e}")


manager = ConnectionManager()
