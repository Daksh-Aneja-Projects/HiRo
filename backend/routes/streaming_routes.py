# /backend/routes/streaming_routes.py - FINAL FIXES (Including SSE Stream)
"""Streaming API Routes for Real-time Communication
Includes SSE for agent streaming and WebSocket for telemetry"""
import asyncio
import json
import logging
import random 
import uuid 
from typing import Dict, Any, Set, Optional 
# CRITICAL REFINEMENT: Import Query to explicitly define nl_prompt type
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query 
from fastapi.responses import StreamingResponse
from services.event_publisher_service import EventPublisherService
from datetime import datetime, timezone 

# CRITICAL FIX: Import the SelfCorrectingAgent for the SSE stream logic
from services.self_correcting_agent import SelfCorrectingAgent 

logger = logging.getLogger(__name__)
# FIX 1: Set the router prefix to match the frontend constant BPCL_STREAM_PATH's base
router = APIRouter(prefix="/streaming")

# WebSocket connection manager
class ConnectionManager:
    # ... (ConnectionManager class remains unchanged) ...
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

# ======================================
# SSE ROUTE: Self-Correcting Agent Stream (Matches frontend BPCL_STREAM_PATH)
# ======================================
# FIX 2: Set the path to /agents/config/stream to match frontend constant BPCL_STREAM_PATH's suffix
@router.get("/agents/config/stream")
# CRITICAL REFINEMENT: Explicitly use Query dependency for nl_prompt
async def stream_agent_configuration(req: Request, nl_prompt: str = Query(..., description="Natural Language prompt for BPCL generation")):
    """Stream self-correcting agent process with real-time thoughts (SSE)"""
    
    # CRITICAL FIX: Use the initialized agent from app.state
    agent: SelfCorrectingAgent = getattr(req.app.state, 'self_correcting_agent', None)
    if not agent: 
        raise HTTPException(status_code=503, detail="Self-Correcting Agent service unavailable.")
    
    async def event_stream():
        try:
            # Stream the agent's thought process
            async for message in agent.generate_and_fix_bpcl(nl_prompt):
                if message == "COMPLETE":
                    # This final completion message is typically the end of the SSE stream
                    # CRITICAL REFINEMENT: The completion message in the service often includes the final code hash, 
                    # but we use the general completion payload here to match the imported service definition.
                    yield f"data: {json.dumps({'status': 'completed', 'timestamp': datetime.now(timezone.utc).isoformat() })}\n\n"
                    break
                
                # The message is expected to be a JSON string from the agent (thought/code/step)
                yield f"data: {message}\n\n"
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Streaming error in config stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'🚨 Error in agent process: {str(e)}', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            yield "data: DONE\n\n"
            
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: str = "anon"):
    """Standard WebSocket entry point. If client_id is missing, generate one."""
    
    if client_id == "anon" or client_id is None:
        client_id = f"anon_ws_{uuid.uuid4().hex[:8]}"
        
    await manager.connect(websocket, client_id)
    
    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "client_id": client_id,
        "message": "Connected to HiRo WebSocket"
    })
    
    try:
        while True:
            # Keep connection alive by waiting for client messages (e.g., subscription requests)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe_telemetry":
                manager.subscribe_telemetry(client_id)
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "channel": "telemetry"
                })

            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket client {client_id} error: {e}")
    finally:
        manager.disconnect(client_id)
