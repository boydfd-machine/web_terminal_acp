from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.platform import ui_events_routes
from app.services.ui_events import UiEventHub


class AuthDbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker) -> None:
        self._client = client
        self.session_factory = session_factory

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._client.patch(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._client.put(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete(*args, **kwargs)


def websocket_auth_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.state.ui_event_hub = UiEventHub()
    test_app.include_router(ui_events_routes.router)
    return test_app


def public_key_pem(private_key) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def keycloak_token(
    private_key,
    *,
    subject: str,
    username: str,
    audience: str = "web-terminal",
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": "https://auth.example.com/realms/home",
            "aud": audience,
            "sub": subject,
            "preferred_username": username,
            "email": f"{username}@example.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


@pytest.fixture
async def auth_db_client(tmp_path):
    database_path = tmp_path / "auth.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.state.auth_session_factory = session_factory
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield AuthDbClient(client, session_factory)
    finally:
        app.dependency_overrides.pop(get_session, None)
        if hasattr(app.state, "auth_session_factory"):
            delattr(app.state, "auth_session_factory")
        await engine.dispose()
