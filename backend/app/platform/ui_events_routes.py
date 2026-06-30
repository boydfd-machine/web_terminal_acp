from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.auth import (
    auth_enabled,
    require_websocket_auth,
    verify_browser_token,
    websocket_auth_subprotocol,
    websocket_session_token,
)
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api", tags=["ui-events"])

_AUTH_QUERY_TOKEN_UNSUPPORTED_MESSAGE = {
    "type": "auth_query_token_unsupported",
    "reason": "reload_required",
}


@router.get("/ui-events")
async def read_ui_events_status(request: Request) -> dict[str, str]:
    ui_event_hub_from_state(request.app.state)
    return {"status": "ok"}


@router.websocket("/ui-events")
async def ui_events_websocket(websocket: WebSocket) -> None:
    if await _park_legacy_query_token_connection(websocket):
        return

    if not await require_websocket_auth(websocket):
        return

    subprotocol = websocket_auth_subprotocol(websocket)
    hub = ui_event_hub_from_state(websocket.app.state)
    try:
        await websocket.accept(subprotocol=subprotocol)
        await websocket.send_json({"type": "connected", "seq": 0})
        await hub.subscribe(websocket.send_text)
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
    except WebSocketDisconnect:
        return
    finally:
        await hub.unsubscribe(websocket.send_text)


async def _park_legacy_query_token_connection(websocket: WebSocket) -> bool:
    if not _has_authenticated_legacy_query_token(websocket):
        return False
    try:
        await websocket.accept()
        await websocket.send_json(_AUTH_QUERY_TOKEN_UNSUPPORTED_MESSAGE)
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return True
    except WebSocketDisconnect:
        return True


def _has_authenticated_legacy_query_token(websocket: WebSocket) -> bool:
    if not auth_enabled():
        return False
    if websocket_session_token(websocket) is not None:
        return False
    token = websocket.query_params.get("auth_token")
    if token is None or not token.strip():
        return False
    return verify_browser_token(token.strip()) is not None
