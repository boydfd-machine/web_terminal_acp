import asyncio

import base64

from contextlib import contextmanager

import json

import threading

import time

from uuid import UUID, uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import select

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from starlette.websockets import WebSocketDisconnect

from app.db import Base

from app.main import app

from app.routers import client_agent as client_agent_router

from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    ClientStatus,
    Event,
    EventSourceType,
    GitWorktreeRun,
    VirtualWindow,
    WindowGitBinding,
    WindowStatus,
)

from app.repositories.clients import create_client, get_client

from app.contexts.windows.infrastructure.repository import create_window

from app.services import git_worktree_coordinator

from app.services.runtime.broker import TerminalBroker

from app.services.runtime.client_connections import ClientConnectionRegistry

from app.services.runtime.protocol import AgentMessage, TerminalPayload, encode_agent_message

class ClientAgentDb:
    def __init__(self, session_factory: async_sessionmaker, client_id: UUID, token: str):
        self.session_factory = session_factory
        self.client_id = client_id
        self.token = token

class FakeElasticsearch:
    def __init__(self, is_committed=None) -> None:
        self.indexed_documents = []
        self.is_committed = is_committed

    async def index(self, **kwargs):
        if self.is_committed is not None:
            assert self.is_committed()
        self.indexed_documents.append(kwargs)
        return {"result": "created"}

class FakeTerminalBroker:
    def __init__(self, *, block_publish: threading.Event | None = None) -> None:
        self.published: list[tuple[UUID, UUID, bytes]] = []
        self.cleared_clients: list[tuple[UUID, str | None]] = []
        self.publish_started = threading.Event()
        self._block_publish = block_publish

    async def publish_output(self, client_id: UUID, window_id: UUID, data: bytes) -> None:
        self.publish_started.set()
        if self._block_publish is not None:
            await asyncio.to_thread(self._block_publish.wait)
        self.published.append((client_id, window_id, data))

    async def publish_status(self, client_id: UUID, window_id: UUID, message: str) -> None:
        self.published.append((client_id, window_id, message.encode("utf-8")))

    async def clear_client(self, client_id: UUID, *, status_message: str | None = None) -> None:
        self.cleared_clients.append((client_id, status_message))

class CaptureUiEventHub:
    def __init__(self) -> None:
        self.invalidations: list[dict[str, object]] = []
        self.debounced_invalidations: list[dict[str, object]] = []

    async def publish_invalidation(
        self,
        resources,
        *,
        client_id=None,
        window_id=None,
        reason=None,
    ) -> None:
        self.invalidations.append(
            {
                "resources": list(resources),
                "client_id": client_id,
                "window_id": window_id,
                "reason": reason,
            }
        )

    async def publish_debounced_invalidation(
        self,
        key,
        resources,
        *,
        client_id=None,
        window_id=None,
        reason=None,
        delay_seconds=1.0,
    ) -> None:
        self.debounced_invalidations.append(
            {
                "key": key,
                "resources": list(resources),
                "client_id": client_id,
                "window_id": window_id,
                "reason": reason,
                "delay_seconds": delay_seconds,
            }
        )

async def create_remote_window(session_factory: async_sessionmaker, client_id: UUID):
    async with session_factory() as session:
        window = await create_window(session, client_id, cwd="/tmp", shell_command="/bin/bash")
        await session.commit()
        return window

async def _event_count(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        return len((await session.execute(select(Event))).scalars().all())

@contextmanager
def connect_client_agent_bulk(test_client: TestClient, client_agent_db: ClientAgentDb):
    with test_client.websocket_connect(
        "/api/client-agent/bulk-ws",
        headers={
            "X-Client-Id": str(client_agent_db.client_id),
            "Authorization": f"Bearer {client_agent_db.token}",
        },
    ) as websocket:
        websocket.send_text(
            encode_agent_message(
                AgentMessage(type="bulk_hello", client_id=client_agent_db.client_id)
            )
        )
        response = websocket.receive_json()
        assert response["type"] == "bulk_hello_ack"
        assert response["client_id"] == str(client_agent_db.client_id)
        assert response.get("request_id") is None
        assert response.get("payload", {}) == {}
        yield websocket

def wait_for_condition(predicate, *, timeout: float = 2.0, interval: float = 0.02) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise TimeoutError("condition was not met before timeout")

def command_marker(window_id: UUID, command: str, *, sequence: int = 1) -> bytes:
    payload = {
        "command": command,
        "shell": "bash",
        "cwd": "/tmp",
        "captured_at": "2026-05-24T00:00:00+00:00",
        "sequence": sequence,
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return (
        f"\x1b]777;web-terminal-command;window_id={window_id};payload={encoded}\x07"
    ).encode("ascii")

def worktree_marker(
    window_id: UUID,
    *,
    worktree_root: str = "/repo/.worktrees/feature",
    main_repo_root: str = "/repo",
    branch: str = "agent/feature",
) -> str:
    payload = {
        "worktree_root": worktree_root,
        "main_repo_root": main_repo_root,
        "branch": branch,
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return f"\x1b]777;web-terminal-worktree;window_id={window_id};payload={encoded}\x07"

@pytest.fixture
def client_agent_db(tmp_path, monkeypatch):
    database_path = tmp_path / "client_agent.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> tuple[UUID, str]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            client, token = await create_client(
                session,
                name="remote",
                runtime=ClientRuntime.remote,
            )
            await session.commit()
            return client.id, token

    client_id, token = asyncio.run(setup())

    monkeypatch.setattr(client_agent_router, "SessionLocal", session_factory)
    monkeypatch.setattr(app.state, "client_connections", ClientConnectionRegistry(), raising=False)
    monkeypatch.setattr(app.state, "terminal_broker", FakeTerminalBroker(), raising=False)

    async def skip_disconnect_db_write(client_id: UUID) -> bool:
        return True

    monkeypatch.setattr(
        client_agent_router,
        "_mark_client_disconnected_by_id",
        skip_disconnect_db_write,
    )
    try:
        yield ClientAgentDb(session_factory, client_id, token)
    finally:
        asyncio.run(engine.dispose())

async def _worktree_binding_exists(
    session_factory: async_sessionmaker,
    window_id: UUID,
) -> bool:
    async with session_factory() as session:
        binding = await session.scalar(
            select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == window_id)
        )
        return binding is not None

async def _set_client_runtime(
    session_factory: async_sessionmaker,
    client_id: UUID,
    runtime: ClientRuntime,
) -> None:
    async with session_factory() as session:
        client = await session.get(Client, client_id)
        assert client is not None
        client.runtime = runtime
        await session.commit()

async def _worktree_diff_contains_commit(
    session_factory: async_sessionmaker,
    window_id: UUID,
) -> bool:
    async with session_factory() as session:
        run = await session.scalar(
            select(GitWorktreeRun).where(GitWorktreeRun.virtual_window_id == window_id)
        )
        diff = run.session_diff_json if run is not None else None
        commits = diff.get("commits") if isinstance(diff, dict) else None
        return bool(commits and commits[0].get("sha") == "feature")

__all__ = [name for name in globals() if not name.startswith("__")]
