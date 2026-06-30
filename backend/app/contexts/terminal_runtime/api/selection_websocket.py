from __future__ import annotations

from uuid import UUID

from fastapi import Depends, WebSocket, WebSocketDisconnect, status

from app.auth import require_websocket_auth, require_websocket_client_access, websocket_auth_subprotocol
from app.contexts.terminal_runtime.api.runtime_dependencies import (
    LOCAL_CLIENT_ID,
    SessionLocal,
    TmuxManager,
    _terminal_selection_hub,
    get_client,
    get_tmux_manager,
    router,
)
from app.contexts.terminal_runtime.api.terminal_websocket import terminal_websocket


async def local_terminal_websocket(
    websocket: WebSocket,
    window_id: UUID,
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> None:
    await terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager)


@router.websocket("/api/clients/{client_id}/terminal-selection")
async def terminal_selection_websocket(websocket: WebSocket, client_id: UUID) -> None:
    if not await require_websocket_auth(websocket):
        return
    if not await require_websocket_client_access(websocket, client_id):
        return

    async with SessionLocal() as session:
        client = await get_client(session, client_id)
        if client is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    subprotocol = websocket_auth_subprotocol(websocket)
    hub = _terminal_selection_hub(websocket)
    await websocket.accept(subprotocol=subprotocol)
    await hub.subscribe(client_id, websocket.send_text)
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
    except WebSocketDisconnect:
        return
    finally:
        await hub.unsubscribe(client_id, websocket.send_text)
