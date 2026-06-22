from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

_DASHBOARD_KEY = "__dashboard__"

_subscribers: dict[str, list[WebSocket]] = {}


async def broadcast_progress(execution_id: str, message: dict[str, Any]):
    """Send progress update to execution subscribers AND dashboard subscribers."""
    for key in (execution_id, _DASHBOARD_KEY):
        subscribers = _subscribers.get(key, [])
        dead = []
        payload = {**message, "execution_id": execution_id} if key == _DASHBOARD_KEY else message
        for ws in subscribers:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            subscribers.remove(ws)


@router.websocket("/ws/qa/{execution_id}")
async def qa_progress_ws(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for live QA execution progress."""
    await websocket.accept()
    _subscribers.setdefault(execution_id, []).append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if execution_id in _subscribers:
            _subscribers[execution_id] = [
                ws for ws in _subscribers[execution_id] if ws != websocket
            ]


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    """WebSocket endpoint for live progress of ALL executions."""
    await websocket.accept()
    _subscribers.setdefault(_DASHBOARD_KEY, []).append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if _DASHBOARD_KEY in _subscribers:
            _subscribers[_DASHBOARD_KEY] = [
                ws for ws in _subscribers[_DASHBOARD_KEY] if ws != websocket
            ]
