import io
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import Base, get_session
from app.main import app
from app.repositories.clients import ensure_local_client
from app.services.polling_response_cache import clear_polling_response_cache
from tests.integration.auth_api_support import (
    auth_db_client,  # noqa: F401 - imported to register the pytest fixture in this module.
    keycloak_token,
    public_key_pem,
)


class DbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker):
        self._client = client
        self.session_factory = session_factory

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._client.put(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._client.patch(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete(*args, **kwargs)


@pytest.fixture
async def db_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clear_polling_response_cache()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    codex_home = tmp_path / ".codex"
    skill_dir = codex_home / "skills" / "docker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: docker\n---\n", encoding="utf-8")
    (codex_home / "AGENTS.md").write_text("Use project rules.\n", encoding="utf-8")

    database_path = tmp_path / "agent_profiles.db"
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
        if hasattr(app.state, "client_connections"):
            delattr(app.state, "client_connections")
        clear_polling_response_cache()
        await engine.dispose()


@pytest.mark.asyncio
async def test_local_agent_profile_lifecycle_and_config_toggle(db_client: DbClient) -> None:
    create_response = await db_client.post(
        "/api/agent-profiles",
        json={
            "name": " Builder ",
            "description": " Main coding profile ",
            "default_agent_client": "codex",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    profile_id = created["id"]
    assert created["name"] == "Builder"
    assert created["description"] == "Main coding profile"
    assert created["default_agent_client"] == "codex"
    assert created["agent_md"] == "Use project rules.\n"

    list_response = await db_client.get("/api/agent-profiles")
    assert list_response.status_code == 200
    assert [profile["id"] for profile in list_response.json()["profiles"]] == [
        profile_id,
        "builtin/developer",
    ]

    patch_response = await db_client.patch(
        f"/api/agent-profiles/{profile_id}",
        json={
            "name": "Reviewer",
            "description": "",
            "agent_md": "Review carefully.\n",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Reviewer"
    assert patched["description"] is None
    assert patched["agent_md"] == "Review carefully.\n"

    config_response = await db_client.get(
        f"/api/clients/00000000-0000-0000-0000-000000000001"
        f"/agent-profiles/{profile_id}/agent-config/codex"
    )
    assert config_response.status_code == 200
    skills = next(section for section in config_response.json()["sections"] if section["id"] == "skills")
    docker_skill = next(item for item in skills["items"] if item["id"] == "docker")
    assert docker_skill["enabled"] is False

    toggle_response = await db_client.patch(
        f"/api/agent-profiles/{profile_id}/agent-config/codex/skills/docker",
        json={"enabled": True},
    )
    assert toggle_response.status_code == 200
    toggled_skills = next(section for section in toggle_response.json()["sections"] if section["id"] == "skills")
    toggled_docker_skill = next(item for item in toggled_skills["items"] if item["id"] == "docker")
    assert toggled_docker_skill["enabled"] is True

    delete_response = await db_client.delete(f"/api/agent-profiles/{profile_id}")
    assert delete_response.status_code == 204
    missing_response = await db_client.get(f"/api/agent-profiles/{profile_id}")
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_local_agent_profiles_are_scoped_by_keycloak_user(
    auth_db_client,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    codex_home = tmp_path / ".codex"
    skill_dir = codex_home / "skills" / "docker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: docker\n---\n", encoding="utf-8")
    (codex_home / "AGENTS.md").write_text("Use project rules.\n", encoding="utf-8")

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

    created = await auth_db_client.post(
        "/api/agent-profiles",
        json={
            "name": "Alice Builder",
            "default_agent_client": "codex",
        },
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob = await auth_db_client.get(
        "/api/agent-profiles",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    alice = await auth_db_client.get(
        "/api/agent-profiles",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert created.status_code == 200
    profile_id = created.json()["id"]
    assert bob.status_code == 200
    bob_profile_ids = [profile["id"] for profile in bob.json()["profiles"]]
    assert profile_id not in bob_profile_ids
    assert "builtin/developer" in bob_profile_ids
    assert alice.status_code == 200
    assert [profile["id"] for profile in alice.json()["profiles"]][0] == profile_id


@pytest.mark.asyncio
async def test_client_scoped_local_agent_profile_routes_use_local_runtime(
    db_client: DbClient,
) -> None:
    clients_response = await db_client.get("/api/clients")
    client_id = clients_response.json()[0]["id"]

    create_response = await db_client.post(
        f"/api/clients/{client_id}/agent-profiles",
        json={"name": "Local Builder", "default_agent_client": "codex"},
    )
    assert create_response.status_code == 200
    profile_id = create_response.json()["id"]

    read_response = await db_client.get(f"/api/clients/{client_id}/agent-profiles/{profile_id}")
    assert read_response.status_code == 200
    assert read_response.json()["name"] == "Local Builder"

    update_response = await db_client.patch(
        f"/api/clients/{client_id}/agent-profiles/{profile_id}",
        json={"default_agent_client": "claude"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["default_agent_client"] == "claude"

    delete_response = await db_client.delete(f"/api/clients/{client_id}/agent-profiles/{profile_id}")
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_builtin_profiles_are_listed_configurable_and_read_only(db_client: DbClient) -> None:
    clients_response = await db_client.get("/api/clients")
    client_id = clients_response.json()[0]["id"]

    list_response = await db_client.get(f"/api/clients/{client_id}/agent-profiles")
    assert list_response.status_code == 200
    profiles = list_response.json()["profiles"]
    assert [profile["id"] for profile in profiles[-1:]] == ["builtin/developer"]
    assert profiles[-1]["name"] == "Developer"

    read_response = await db_client.get(
        f"/api/clients/{client_id}/agent-profiles/detail",
        params={"profile_id": "builtin/developer"},
    )
    assert read_response.status_code == 200
    assert read_response.json()["default_agent_client"] == "codex"

    config_response = await db_client.get(
        f"/api/clients/{client_id}/agent-profile-config",
        params={"profile_id": "builtin/developer", "agent": "codex"},
    )
    assert config_response.status_code == 200
    developer_config = config_response.json()
    developer_skills = next(section for section in developer_config["sections"] if section["id"] == "skills")
    developer_skill_items = {item["id"]: item for item in developer_skills["items"]}
    assert developer_skill_items["frontend-development"]["enabled"] is True
    assert developer_skill_items["backend-development"]["enabled"] is True
    assert developer_skill_items["tdd"]["enabled"] is True
    assert developer_skill_items["deep-research"]["enabled"] is True
    assert developer_skill_items["docker"]["enabled"] is False

    toggle_response = await db_client.patch(
        f"/api/clients/{client_id}/agent-profile-config/codex/skills/docker",
        params={"profile_id": "builtin/developer"},
        json={"enabled": True},
    )
    assert toggle_response.status_code == 200
    toggled_skills = next(section for section in toggle_response.json()["sections"] if section["id"] == "skills")
    toggled_docker = next(item for item in toggled_skills["items"] if item["id"] == "docker")
    assert toggled_docker["enabled"] is True

    update_response = await db_client.patch(
        f"/api/clients/{client_id}/agent-profiles/detail",
        params={"profile_id": "builtin/developer"},
        json={"name": "Mutable"},
    )
    assert update_response.status_code == 400
    delete_response = await db_client.delete(
        f"/api/clients/{client_id}/agent-profiles/detail",
        params={"profile_id": "builtin/developer"},
    )
    assert delete_response.status_code == 400


@pytest.mark.asyncio
async def test_client_agent_profile_config_materializes_system_skills_from_database(
    db_client: DbClient,
) -> None:
    clients_response = await db_client.get("/api/clients")
    client_id = clients_response.json()[0]["id"]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("fuck-shit-mountain/SKILL.md", "---\nname: fuck shit mountain\n---\n")

    upload_response = await db_client.put(
        "/api/system-agent-config/skills/fuck-shit-mountain",
        content=archive.getvalue(),
        headers={"Content-Type": "application/zip"},
    )
    assert upload_response.status_code == 200
    system_config_root = Path.home() / ".web-terminal-acp" / "system-config"
    for path in sorted(system_config_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    system_config_root.rmdir()

    config_response = await db_client.get(
        f"/api/clients/{client_id}/agent-profile-config",
        params={"profile_id": "builtin/developer", "agent": "codex"},
    )

    assert config_response.status_code == 200
    skills = next(section for section in config_response.json()["sections"] if section["id"] == "skills")
    system_skill = next(item for item in skills["items"] if item["id"] == "fuck-shit-mountain")
    assert system_skill["name"] == "fuck shit mountain"
    assert system_skill["enabled"] is True
    assert system_skill["origin"] == "system_config"


@pytest.mark.asyncio
async def test_system_agent_config_api_uploads_downloads_and_toggles_skill(
    db_client: DbClient,
) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("ship-it/SKILL.md", "---\nname: Ship It\n---\n")

    upload_response = await db_client.put(
        "/api/system-agent-config/skills/ship-it",
        content=archive.getvalue(),
        headers={"Content-Type": "application/zip"},
    )
    assert upload_response.status_code == 200
    skills = next(section for section in upload_response.json()["sections"] if section["id"] == "skills")
    ship_it = next(item for item in skills["items"] if item["id"] == "ship-it")
    assert ship_it["enabled"] is True

    toggle_response = await db_client.patch(
        "/api/system-agent-config/skills/ship-it",
        json={"enabled": False},
    )
    assert toggle_response.status_code == 200
    toggled_skills = next(section for section in toggle_response.json()["sections"] if section["id"] == "skills")
    toggled_ship_it = next(item for item in toggled_skills["items"] if item["id"] == "ship-it")
    assert toggled_ship_it["enabled"] is False

    download_response = await db_client.get("/api/system-agent-config/skills/ship-it/download")
    assert download_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download_response.content)) as downloaded:
        assert "ship-it/SKILL.md" in downloaded.namelist()

    detail_response = await db_client.get("/api/system-agent-config/skills/ship-it/detail")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["editable"] is True
    assert detail["origin"] == "system_config"
    assert [entry["path"] for entry in detail["entries"]] == ["SKILL.md"]
    assert detail["files"][0]["content"] == "---\nname: Ship It\n---\n"

    edit_response = await db_client.patch(
        "/api/system-agent-config/skills/ship-it/files",
        json={"path": "SKILL.md", "content": "---\nname: Ship Again\n---\n"},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["files"][0]["content"] == "---\nname: Ship Again\n---\n"


@pytest.mark.asyncio
async def test_system_agent_config_api_upserts_and_deletes_mcp(db_client: DbClient) -> None:
    upsert_response = await db_client.put(
        "/api/system-agent-config/mcp",
        json={
            "id": "filesystem",
            "server": {"type": "stdio", "command": "echo", "args": ["ok"]},
            "enabled": True,
        },
    )
    assert upsert_response.status_code == 200
    mcp = next(section for section in upsert_response.json()["sections"] if section["id"] == "mcp")
    filesystem = next(item for item in mcp["items"] if item["id"] == "filesystem")
    assert filesystem["enabled"] is True

    detail_response = await db_client.get("/api/system-agent-config/mcp/filesystem/detail")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["editable"] is True
    assert detail["server"] == {"type": "stdio", "command": "echo", "args": ["ok"]}
    assert detail["tools"] == []

    delete_response = await db_client.delete("/api/system-agent-config/mcp/filesystem")
    assert delete_response.status_code == 200
    deleted_mcp = next(section for section in delete_response.json()["sections"] if section["id"] == "mcp")
    assert all(item["id"] != "filesystem" for item in deleted_mcp["items"])


@pytest.mark.asyncio
async def test_system_agent_config_api_reads_builtin_detail_without_web_terminal_mcp(
    db_client: DbClient,
) -> None:
    skill_response = await db_client.get("/api/system-agent-config/skills/web-terminal-acp-ops/detail")
    assert skill_response.status_code == 200
    skill = skill_response.json()
    assert skill["editable"] is True
    assert skill["origin"] == "system_builtin"
    assert any(file["path"] == "SKILL.md" and file["editable"] is True for file in skill["files"])

    mcp_response = await db_client.get("/api/system-agent-config/mcp/web-terminal-acp-mcp/detail")
    assert mcp_response.status_code == 404
