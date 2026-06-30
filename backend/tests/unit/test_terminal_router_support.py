import asyncio

import contextlib

from types import SimpleNamespace

from uuid import uuid4

import pytest

from fastapi import status

from fastapi.websockets import WebSocketDisconnect

from app.models import LOCAL_CLIENT_ID, VirtualWindow, WindowStatus

from app.routers import terminal

from app.routers.terminal import mark_window_active, mark_window_disconnected, mark_window_error

from app.services.runtime.types import RuntimeWindow

class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self) -> None:
        return None

class FakeWebSocket:
    def __init__(self, messages=None) -> None:
        self.messages = list(messages or [])
        self.accepted = False
        self.accepted_subprotocol: str | None = None
        self.closed: list[int] = []
        self.headers = {}
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.app = SimpleNamespace(state=SimpleNamespace(es_indexes_ready=False, es_client=None))

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True
        self.accepted_subprotocol = subprotocol

    async def close(self, code: int = 1000) -> None:
        self.closed.append(code)

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self):
        if not self.messages:
            raise WebSocketDisconnect(code=1000)
        return self.messages.pop(0)

class ExistingTmuxManager:
    async def has_window(self, target) -> bool:
        return True

class FakeBroker:
    def __init__(self) -> None:
        self.subscriptions = []
        self.unsubscriptions = []
        self.attachments = []
        self.inputs = []
        self.resizes = []
        self.registered = []
        self.published_output = []

    def register_runtime(self, client_id, runtime) -> None:
        self.registered.append((client_id, runtime))

    async def subscribe(self, client_id, window_id, sender, status_sender=None) -> None:
        self.subscriptions.append((client_id, window_id, sender, status_sender))

    async def unsubscribe(self, client_id, window_id, sender, status_sender=None) -> None:
        self.unsubscriptions.append((client_id, window_id, sender, status_sender))

    async def attach(
        self,
        client_id,
        window_id,
        runtime_window,
        output_callback=None,
        selection_callback=None,
        view_id=None,
        allow_missing_window_recreate: bool = False,
    ):
        self.attachments.append(
            (client_id, window_id, runtime_window, output_callback, selection_callback, view_id)
        )
        return runtime_window

    async def send_input(self, client_id, window_id, runtime_window, data: bytes, view_id=None) -> None:
        self.inputs.append((client_id, window_id, runtime_window, data, view_id))

    async def resize(self, client_id, window_id, runtime_window, *, cols: int, rows: int, view_id=None) -> None:
        self.resizes.append((client_id, window_id, runtime_window, cols, rows, view_id))

    async def publish_output(self, client_id, window_id, data: bytes) -> None:
        self.published_output.append((client_id, window_id, data))

    async def publish_view_output(self, client_id, view_id, data: bytes) -> None:
        self.published_output.append((client_id, view_id, data))

    async def acknowledge_output(self, client_id, window_id, sender, bytes_acked=None) -> None:
        return None

    async def select_window(
        self,
        client_id,
        view_id,
        current_window_id,
        current_runtime_window,
        next_window_id,
        next_runtime_window,
        allow_missing_window_recreate: bool = False,
    ):
        return next_runtime_window

    async def clear_client(self, client_id, *, status_message=None) -> None:
        return None

__all__ = [name for name in globals() if not name.startswith("__")]
