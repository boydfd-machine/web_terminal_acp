import traceback

from pathlib import Path

from uuid import uuid4

import pytest

from fastapi import HTTPException

from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sqlalchemy import select

from app.db import Base, get_session

from app.main import app

from app.models import (
    AiSession,
    Client,
    ClientRegistrationKey,
    ClientRegistrationKeyStatus,
    ClientRuntime,
    Event,
    EventSourceType,
    Folder,
    ProjectSummary,
    SummaryJob,
    TerminalNotificationState,
    TerminalRecentUsage,
    VirtualWindow,
)

from app.repositories.client_registration_keys import create_registration_key

from app.routers import clients as clients_router

from app.repositories.clients import create_client, ensure_local_client

from app.repositories.folders import get_or_create_folder_by_path

from app.contexts.windows.infrastructure.repository import create_window

from app.schemas import BootstrapClientIn

from app.services import polling_response_cache

from app.services.polling_response_cache import clear_polling_response_cache

from app.services.bootstrap.installer import BootstrapConnectionError, BootstrapDependencyError

from app.version import __version__

class DbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker):
        self._client = client
        self.session_factory = session_factory

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._client.patch(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete(*args, **kwargs)

class FakeClientConnection:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True

class FakeClientConnectionRegistry:
    def __init__(self, connection: FakeClientConnection | None) -> None:
        self.connection = connection
        self.unregistered: list[tuple[object, object]] = []

    def get(self, _client_id):
        return self.connection

    async def unregister(self, client_id, connection) -> None:
        self.unregistered.append((client_id, connection))
        if connection is self.connection:
            self.connection = None

@pytest.fixture
async def db_client(tmp_path):
    clear_polling_response_cache()
    database_path = tmp_path / "clients.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await ensure_local_client(session)
        await session.commit()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield DbClient(test_client, session_factory)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(clients_router.get_bootstrap_runner, None)
        app.dependency_overrides.pop(clients_router.get_update_runner, None)
        if hasattr(app.state, "client_connections"):
            delattr(app.state, "client_connections")
        clear_polling_response_cache()
        await engine.dispose()

BOOTSTRAP_PAYLOAD = {
    "name": "Remote Dev",
    "host": "dev.example.com",
    "port": 22,
    "username": "alice",
    "private_key": "ssh-private-key-placeholder",
    "passphrase": "ssh-passphrase",
    "server_url": "https://control.example.com",
}

REPO_ROOT = Path(__file__).resolve().parents[3]

def _formatted_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

class CommitRecorder:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
