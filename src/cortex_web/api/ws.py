from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# Simple in-memory pub/sub for execution progress
_subscribers: dict[str, list[WebSocket]] = {}


async def broadcast_progress(execution_id: str, message: dict[str, Any]):
    """Send progress update to all subscribers of an execution."""
    subscribers = _subscribers.get(execution_id, [])
    dead = []
    for ws in subscribers:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        subscribers.remove(ws)


@router.websocket("/ws/qa/{execution_id}")
async def qa_progress_ws(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for live QA execution progress."""
    await websocket.accept()

    if execution_id not in _subscribers:
        _subscribers[execution_id] = []
    _subscribers[execution_id].append(websocket)

    try:
        while True:
            # Keep connection alive, wait for client messages (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if execution_id in _subscribers:
            _subscribers[execution_id] = [
                ws for ws in _subscribers[execution_id] if ws != websocket
            ]
