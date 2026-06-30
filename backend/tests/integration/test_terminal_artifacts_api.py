from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.model_base import Base
from app.models import TerminalArtifactStatus
from app.repositories.clients import ensure_local_client
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_succeeded
from app.contexts.windows.infrastructure.repository import create_window
from app.routers import terminal_artifacts as terminal_artifacts_router
from app.services.polling_response_cache import clear_polling_response_cache


@pytest.fixture
async def artifact_client(tmp_path, monkeypatch):
    database_path = tmp_path / "terminal-artifacts.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/workspace", shell_command="codex")
        client_id = client.id
        window_id = window.id
        await session.commit()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    scheduled = []

    def fake_schedule(request, **kwargs):
        scheduled.append(request)

    monkeypatch.setattr(terminal_artifacts_router, "schedule_terminal_artifact_generation", fake_schedule)
    app.dependency_overrides[get_session] = override_get_session
    clear_polling_response_cache()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session_factory, str(client_id), str(window_id), scheduled
    finally:
        app.dependency_overrides.pop(get_session, None)
        clear_polling_response_cache()
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_terminal_artifact_returns_pending_and_schedules_generation(artifact_client):
    client, _session_factory, client_id, window_id, scheduled = artifact_client

    response = await client.post(
        f"/api/clients/{client_id}/windows/{window_id}/artifacts",
        json={
            "artifact_kind": "agent_trace_graph",
            "metadata_json": {"source": "test"},
            "output_language": "English",
            "terminal_retention_seconds": 120,
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["artifact_kind"] == "agent_trace_graph"
    assert body["status"] == TerminalArtifactStatus.pending.value
    assert body["metadata_json"] == {"source": "test", "terminal_retention_seconds": 120.0}
    assert body["display_html"] is None
    assert len(scheduled) == 1
    assert str(scheduled[0].artifact_id) == body["id"]
    assert scheduled[0].output_language == "English"


@pytest.mark.asyncio
async def test_create_agent_pitfalls_artifact_rejects_removed_builtin_kind(artifact_client):
    client, _session_factory, client_id, window_id, scheduled = artifact_client

    response = await client.post(
        f"/api/clients/{client_id}/windows/{window_id}/artifacts",
        json={"artifact_kind": "agent_pitfalls"},
    )

    assert response.status_code == 400
    assert "unsupported terminal artifact kind" in response.json()["detail"]
    assert scheduled == []


@pytest.mark.asyncio
async def test_create_terminal_artifact_rejects_unknown_kind(artifact_client):
    client, _session_factory, client_id, window_id, scheduled = artifact_client

    response = await client.post(
        f"/api/clients/{client_id}/windows/{window_id}/artifacts",
        json={"artifact_kind": "unknown-kind"},
    )

    assert response.status_code == 400
    assert scheduled == []


@pytest.mark.asyncio
async def test_local_terminal_artifact_route_uses_local_client(artifact_client):
    client, _session_factory, client_id, window_id, scheduled = artifact_client

    response = await client.post(
        f"/api/windows/{window_id}/artifacts",
        json={"artifact_kind": "agent_trace_graph"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["client_id"] == client_id
    assert body["virtual_window_id"] == window_id
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_terminal_artifact_list_omits_html_but_html_endpoint_returns_it(artifact_client):
    client, session_factory, client_id, window_id, _scheduled = artifact_client
    async with session_factory() as session:
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=UUID(window_id),
            source_window_id=UUID(window_id),
            artifact_kind="agent_trace_graph",
            title="Trace",
        )
        await mark_artifact_succeeded(
            session,
            artifact,
            content_json={"task": "demo", "goals": [], "nodes": [], "edges": []},
            display_html="<html><body>trace</body></html>",
        )
        artifact_id = artifact.id
        await session.commit()

    list_response = await client.get(f"/api/clients/{client_id}/windows/{window_id}/artifacts")
    assert list_response.status_code == 200
    listed = list_response.json()["artifacts"][0]
    assert listed["id"] == str(artifact_id)
    assert listed["display_html"] is None

    detail_response = await client.get(
        f"/api/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["display_html"] == "<html><body>trace</body></html>"

    html_response = await client.get(
        f"/api/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}/html"
    )
    assert html_response.status_code == 200
    assert "trace" in html_response.text


@pytest.mark.asyncio
async def test_terminal_artifact_html_requires_bearer_auth(artifact_client):
    client, session_factory, client_id, window_id, _scheduled = artifact_client
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        async with session_factory() as session:
            artifact = await create_terminal_artifact(
                session,
                client_id=UUID(client_id),
                virtual_window_id=UUID(window_id),
                source_window_id=UUID(window_id),
                artifact_kind="agent_trace_graph",
                title="Trace",
            )
            await mark_artifact_succeeded(
                session,
                artifact,
                content_json={"task": "demo", "goals": [], "nodes": [], "edges": []},
                display_html="<html><body>trace</body></html>",
            )
            artifact_id = artifact.id
            await session.commit()

        login = await client.post("/api/auth/login", json={"secret": "login-secret"})
        token = login.json()["token"]
        query_token_rejected = await client.get(
            f"/api/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}/html?auth_token={token}"
        )
        accepted = await client.get(
            f"/api/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}/html",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert query_token_rejected.status_code == 401
    assert accepted.status_code == 200
    assert "trace" in accepted.text
