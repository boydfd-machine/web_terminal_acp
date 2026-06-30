from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.websockets import WebSocketDisconnect

from app.contexts.terminal_runtime.api import aux_terminal_routes
from app.models import ClientRuntime, LOCAL_CLIENT_ID, VirtualWindow, WindowStatus


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class FakeWebSocket:
    def __init__(self, *, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}
        self.query_params = {}
        self.app = SimpleNamespace(state=SimpleNamespace())
        self.accepted = False
        self.accepted_subprotocol: str | None = None
        self.sent_text: list[str] = []
        self.closed: list[int] = []

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True
        self.accepted_subprotocol = subprotocol

    async def close(self, code: int = 1000) -> None:
        self.closed.append(code)

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        return None

    async def receive(self):
        raise WebSocketDisconnect(code=1000)


@pytest.mark.asyncio
async def test_aux_terminal_websocket_accepts_requested_auth_subprotocol(monkeypatch) -> None:
    window_id = uuid4()
    token_protocol = "web-terminal-auth.token-1"
    websocket = FakeWebSocket(headers={"sec-websocket-protocol": token_protocol})
    window = VirtualWindow(
        id=window_id,
        client_id=LOCAL_CLIENT_ID,
        title="Terminal",
        status=WindowStatus.active,
    )
    client = SimpleNamespace(runtime=ClientRuntime.local)
    attached: list[object] = []
    detached: list[object] = []

    async def fake_get_client(session, requested_client_id):
        assert requested_client_id == LOCAL_CLIENT_ID
        return client

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == LOCAL_CLIENT_ID
        assert requested_window_id == window_id
        return window

    class FakeAuxRegistry:
        async def local_runtime(self, requested_client_id, requested_window_id, *, cwd, shell_command):
            assert requested_client_id == LOCAL_CLIENT_ID
            assert requested_window_id == window_id
            return SimpleNamespace(cwd=cwd, shell_command=shell_command)

    async def fake_attach_local_aux_terminal(runtime, send_bytes):
        attachment = SimpleNamespace(runtime=runtime, send_bytes=send_bytes)
        attached.append(attachment)
        return attachment

    async def fake_detach_local_aux_terminal(attachment):
        detached.append(attachment)

    monkeypatch.setattr(aux_terminal_routes, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(aux_terminal_routes, "get_client", fake_get_client)
    monkeypatch.setattr(aux_terminal_routes, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(aux_terminal_routes, "aux_terminal_registry_from_state", lambda state: FakeAuxRegistry())
    monkeypatch.setattr(aux_terminal_routes, "attach_local_aux_terminal", fake_attach_local_aux_terminal)
    monkeypatch.setattr(aux_terminal_routes, "detach_local_aux_terminal", fake_detach_local_aux_terminal)

    await aux_terminal_routes.aux_terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id)

    assert websocket.accepted is True
    assert websocket.accepted_subprotocol == token_protocol
    assert websocket.sent_text == [
        '{"type":"terminal_status","status":"connecting"}',
        '{"type":"terminal_status","status":"connected"}',
    ]
    assert detached == attached

