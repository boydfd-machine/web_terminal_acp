import io
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import Base, get_session
from app.main import app
from app.models import UiSetting
from tests.integration.auth_api_support import (
    auth_db_client,
    keycloak_token,
    public_key_pem,
)


class DbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker):
        self._client = client
        self.session_factory = session_factory

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._client.put(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete(*args, **kwargs)


@pytest.fixture
async def db_client(tmp_path):
    database_path = tmp_path / "ui-settings.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

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
        await engine.dispose()


@pytest.mark.asyncio
async def test_custom_quick_keys_round_trip(db_client):
    initial = await db_client.get("/api/ui-settings/custom-quick-keys")
    assert initial.status_code == 200
    assert initial.json() == {"quick_keys": []}

    payload = {
        "quick_keys": [
            {"id": "status", "label": "Git status", "input": "git status{Enter}"},
            {
                "id": "interrupt",
                "label": "Interrupt",
                "input": "{Ctrl-C}",
                "shortcut": {"key": "c", "alt": True},
            },
        ]
    }
    saved = await db_client.put("/api/ui-settings/custom-quick-keys", json=payload)
    assert saved.status_code == 200
    assert saved.json() == payload

    loaded = await db_client.get("/api/ui-settings/custom-quick-keys")
    assert loaded.status_code == 200
    assert loaded.json() == payload


@pytest.mark.asyncio
async def test_custom_quick_keys_reject_invalid_items(db_client):
    response = await db_client.put(
        "/api/ui-settings/custom-quick-keys",
        json={"quick_keys": [{"id": "bad", "label": "", "input": "pwd"}]},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_app_preferences_are_scoped_by_keycloak_user(auth_db_client, monkeypatch):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", public_key_pem(key_pair))
    alice_token = keycloak_token(key_pair, subject="alice", username="alice")
    bob_token = keycloak_token(key_pair, subject="bob", username="bob")

    payload = {
        "app_locale": "en-US",
        "summary_output_language": "English",
        "terminal_grouping_mode": "time-topic",
        "terminal_time_range": "14d",
        "artifact_terminal_retention_seconds": 120,
        "theme_skin": "raycast",
        "desktop_notifications_enabled": True,
        "agent_command_settings": {"codex": "codex --search"},
        "agent_model_selection_settings": {
            "codex": {"preset_id": "openai-main", "model": "gpt-5"}
        },
        "artifact_model_selection_settings": {
            "codex": {
                "preset_id": "openai-artifacts",
                "model": "gpt-5-mini",
                "codex_model_reasoning_effort": "high",
            }
        },
        "keyboard_shortcut_bindings": {"settings": {"key": "s", "ctrl": True}},
    }

    saved = await auth_db_client.put(
        "/api/ui-settings/app-preferences",
        json=payload,
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob = await auth_db_client.get(
        "/api/ui-settings/app-preferences",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    alice = await auth_db_client.get(
        "/api/ui-settings/app-preferences",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert bob.status_code == 200
    assert bob.json()["configured"] is False
    assert bob.json()["theme_skin"] == "default"
    assert alice.status_code == 200
    assert alice.json()["configured"] is True
    assert alice.json()["theme_skin"] == "raycast"
    assert alice.json()["artifact_model_selection_settings"] == {
        "codex": {
            "preset_id": "openai-artifacts",
            "model": "gpt-5-mini",
            "codex_model_reasoning_effort": "high",
        }
    }
    assert alice.json()["keyboard_shortcut_bindings"] == {
        "settings": {"key": "s", "ctrl": True}
    }


@pytest.mark.asyncio
async def test_system_model_presets_are_scoped_by_keycloak_user(auth_db_client, monkeypatch):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", public_key_pem(key_pair))
    alice_token = keycloak_token(key_pair, subject="alice", username="alice")
    bob_token = keycloak_token(key_pair, subject="bob", username="bob")

    payload = {
        "name": "Alice Models",
        "providers": ["openai_compatible"],
        "base_url": "https://alice.example.com/v1",
        "api_key": "alice-key",
        "models": ["alice-model"],
    }

    saved = await auth_db_client.put(
        "/api/system-agent-config/model-presets/alice-main",
        json=payload,
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob = await auth_db_client.get(
        "/api/system-agent-config/model-presets",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    alice = await auth_db_client.get(
        "/api/system-agent-config/model-presets",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert saved.status_code == 200
    assert bob.status_code == 200
    assert bob.json()["presets"] == []
    assert alice.status_code == 200
    assert [preset["id"] for preset in alice.json()["presets"]] == ["alice-main"]


@pytest.mark.asyncio
async def test_system_model_presets_round_trip_uses_database(db_client, tmp_path, monkeypatch):
    first_home = tmp_path / "first-home"
    second_home = tmp_path / "second-home"
    monkeypatch.setattr(Path, "home", lambda: first_home)

    payload = {
        "name": "OpenAI Main",
        "providers": ["openai_compatible", "anthropic_compatible"],
        "base_url": "https://models.example.com/v1",
        "api_key": "secret-key",
        "models": ["model-a"],
        "model_configs": [
            {
                "name": "model-a",
                "max_output_tokens": 4096,
                "context_window": 128000,
                "auto_compact_token_limit": 96000,
            }
        ],
    }
    saved = await db_client.put("/api/system-agent-config/model-presets/openai-main", json=payload)
    assert saved.status_code == 200

    async with db_client.session_factory() as session:
        setting = await session.get(UiSetting, "system_model_presets")
        assert setting is not None
        assert "openai-main" in setting.value_json["presets"]

    monkeypatch.setattr(Path, "home", lambda: second_home)
    loaded = await db_client.get("/api/system-agent-config/model-presets")

    assert loaded.status_code == 200
    assert loaded.json()["presets"] == [
        {
            "id": "openai-main",
            "name": "OpenAI Main",
            "provider": "openai_compatible",
            "providers": ["openai_compatible", "anthropic_compatible"],
            "base_url": "https://models.example.com/v1",
            "api_key": "secret-key",
            "models": ["model-a"],
            "model_configs": [
                {
                    "name": "model-a",
                    "max_output_tokens": 4096,
                    "context_window": 128000,
                    "auto_compact_token_limit": 96000,
                }
            ],
        }
    ]
    assert not (first_home / ".web-terminal-acp" / "system-config" / "model-presets.json").exists()


@pytest.mark.asyncio
async def test_system_model_preset_export_import_round_trip(db_client):
    payload = {
        "name": "OpenAI Main",
        "providers": ["openai_compatible"],
        "base_url": "https://models.example.com/v1",
        "api_key": "secret-key",
        "models": ["model-a"],
        "model_configs": [{"name": "model-a", "codex_model_reasoning_effort": "high"}],
    }
    saved = await db_client.put("/api/system-agent-config/model-presets/openai-main", json=payload)
    assert saved.status_code == 200

    exported = await db_client.get("/api/system-agent-config/model-presets/openai-main/export")
    assert exported.status_code == 200
    bundle = exported.json()
    assert bundle["kind"] == "web-terminal-model-preset"
    assert bundle["preset"]["id"] == "openai-main"
    assert exported.headers["content-disposition"] == 'attachment; filename="openai-main.json"'

    delete_response = await db_client.delete("/api/system-agent-config/model-presets/openai-main")
    assert delete_response.status_code == 200

    imported = await db_client.post("/api/system-agent-config/model-presets/import", json=bundle)
    assert imported.status_code == 200
    assert imported.json()["presets"][0] == {
        "id": "openai-main",
        "name": "OpenAI Main",
        "provider": "openai_compatible",
        "providers": ["openai_compatible"],
        "base_url": "https://models.example.com/v1",
        "api_key": "secret-key",
        "models": ["model-a"],
        "model_configs": [{"name": "model-a", "codex_model_reasoning_effort": "high"}],
    }


@pytest.mark.asyncio
async def test_system_model_presets_import_legacy_file_to_database(db_client, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy_path = tmp_path / ".web-terminal-acp" / "system-config" / "model-presets.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps({
            "presets": {
                "legacy-main": {
                    "name": "Legacy Main",
                    "provider": "openai_compatible",
                    "providers": ["openai_compatible"],
                    "base_url": "https://legacy.example.com/v1",
                    "api_key": "legacy-key",
                    "models": ["legacy-model"],
                }
            }
        }),
        encoding="utf-8",
    )

    loaded = await db_client.get("/api/system-agent-config/model-presets")

    assert loaded.status_code == 200
    assert loaded.json()["presets"][0]["id"] == "legacy-main"
    async with db_client.session_factory() as session:
        setting = await session.get(UiSetting, "system_model_presets")
        assert setting is not None
        assert "legacy-main" in setting.value_json["presets"]


@pytest.mark.asyncio
async def test_system_agent_config_mcp_round_trip_uses_database(db_client, tmp_path, monkeypatch):
    first_home = tmp_path / "first-home"
    second_home = tmp_path / "second-home"
    monkeypatch.setattr(Path, "home", lambda: first_home)

    saved = await db_client.put(
        "/api/system-agent-config/mcp",
        json={
            "id": "system-echo",
            "server": {"type": "stdio", "command": "echo", "args": ["ok"]},
            "enabled": True,
        },
    )
    assert saved.status_code == 200

    async with db_client.session_factory() as session:
        setting = await session.get(UiSetting, "system_agent_config_files")
        assert setting is not None
        paths = {item["path"] for item in setting.value_json["files"]}
        assert "mcp.json" in paths

    monkeypatch.setattr(Path, "home", lambda: second_home)
    loaded = await db_client.get("/api/system-agent-config")

    assert loaded.status_code == 200
    mcp = next(section for section in loaded.json()["sections"] if section["id"] == "mcp")
    item = next(candidate for candidate in mcp["items"] if candidate["id"] == "system-echo")
    assert item["enabled"] is True
    detail = await db_client.get("/api/system-agent-config/mcp/system-echo/detail")
    assert detail.status_code == 200
    assert detail.json()["server"]["args"] == ["ok"]


@pytest.mark.asyncio
async def test_system_agent_config_skill_upload_round_trip_uses_database(db_client, tmp_path, monkeypatch):
    first_home = tmp_path / "first-home"
    second_home = tmp_path / "second-home"
    monkeypatch.setattr(Path, "home", lambda: first_home)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("review-helper/SKILL.md", "---\nname: Review Helper\n---\n")
        archive.writestr("review-helper/scripts/run.sh", "echo ok\n")

    saved = await db_client.put(
        "/api/system-agent-config/skills/review-helper",
        content=archive_buffer.getvalue(),
        headers={"content-type": "application/zip"},
    )
    assert saved.status_code == 200

    async with db_client.session_factory() as session:
        setting = await session.get(UiSetting, "system_agent_config_files")
        assert setting is not None
        paths = {item["path"] for item in setting.value_json["files"]}
        assert "skills/review-helper/SKILL.md" in paths

    monkeypatch.setattr(Path, "home", lambda: second_home)
    detail = await db_client.get("/api/system-agent-config/skills/review-helper/detail")

    assert detail.status_code == 200
    assert detail.json()["name"] == "Review Helper"
    files = {item["path"]: item for item in detail.json()["files"]}
    assert files["scripts/run.sh"]["content"] == "echo ok\n"
