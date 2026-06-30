from uuid import uuid4

import asyncio

import pytest

from app.services.runtime.client_connections import ClientConnectionClosed

from app.services.runtime.protocol import AgentMessage, TerminalPayload

from app.services.runtime.remote import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError

from app.services.runtime.types import RuntimeWindow

class FakeRegistry:
    def __init__(self, connection=None) -> None:
        self.connection = connection
        self.requested_client_ids = []

    def get(self, client_id):
        self.requested_client_ids.append(client_id)
        return self.connection

class FakeConnection:
    def __init__(self, response: AgentMessage | None = None) -> None:
        self.response = response
        self.requests: list[tuple[AgentMessage, float]] = []
        self.sent: list[AgentMessage] = []

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append((message, timeout))
        assert self.response is not None
        return self.response

    async def send(self, message: AgentMessage) -> None:
        self.sent.append(message)

class ClosedConnection(FakeConnection):
    closed = True

class TimeoutConnection(FakeConnection):
    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        raise asyncio.TimeoutError

class ClosingConnection(FakeConnection):
    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        raise ClientConnectionClosed("closed")

__all__ = [name for name in globals() if not name.startswith("__")]
