from tests.integration.test_client_api_support import *
from uuid import UUID

@pytest.mark.asyncio
async def test_bootstrap_client_route_rejects_invalid_port(db_client):
    response = await db_client.post(
        "/api/clients/bootstrap", json={**BOOTSTRAP_PAYLOAD, "port": 70000}
    )

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_registration_key_is_single_use_for_direct_client_registration(db_client):
    async with db_client.session_factory() as session:
        registration_key, key = await create_registration_key(session, label="dev box")
        key_id = registration_key.id
        await session.commit()

    payload = {
        "registration_key": key,
        "name": "Direct Dev",
        "hostname": "direct-host",
        "install_path": "/home/alice/.web-terminal-acp",
        "server_url": "https://control.example.com",
    }
    first = await db_client.post("/api/clients/register", json=payload)
    second = await db_client.post("/api/clients/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 401
    body = first.json()
    assert body["name"] == "Direct Dev"
    assert body["token"]
    assert body["config"]["client_id"] == body["client_id"]
    assert body["config"]["token"] == body["token"]
    assert body["config"]["server_id"]
    assert body["config"]["server_key"]
    assert (
        body["config"]["install_path"]
        == "/home/alice/.web-terminal-acp/servers/" + body["config"]["server_key"]
    )
    assert "client_agent/runner/__init__.py" in body["package"]["files"]
    assert "client_agent/runner/lifecycle.py" in body["package"]["files"]

    async with db_client.session_factory() as session:
        used_key = await session.get(ClientRegistrationKey, key_id)
        assert used_key is not None
        assert used_key.status is ClientRegistrationKeyStatus.used
        assert str(used_key.used_client_id) == body["client_id"]

@pytest.mark.asyncio
async def test_direct_client_registration_reuses_existing_client_with_same_name(db_client):
    async with db_client.session_factory() as session:
        first_registration_key, first_key = await create_registration_key(session, label="desk")
        second_registration_key, second_key = await create_registration_key(session, label="desk")
        await session.commit()

    first_payload = {
        "registration_key": first_key,
        "name": "Office Mac Mini",
        "hostname": "old-host",
        "install_path": "/home/alice/.web-terminal-acp",
        "server_url": "https://control.example.com",
    }
    second_payload = {
        **first_payload,
        "registration_key": second_key,
        "hostname": "new-host",
        "install_path": "/srv/web-terminal-acp",
    }

    first = await db_client.post("/api/clients/register", json=first_payload)
    second = await db_client.post("/api/clients/register", json=second_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["client_id"] == first_body["client_id"]
    assert second_body["token"] != first_body["token"]
    assert (
        second_body["config"]["install_path"]
        == "/srv/web-terminal-acp/servers/" + second_body["config"]["server_key"]
    )

    async with db_client.session_factory() as session:
        clients = list(await session.scalars(select(Client)))
        remote_clients = [client for client in clients if client.runtime is ClientRuntime.remote]
        first_used_key = await session.get(ClientRegistrationKey, first_registration_key.id)
        second_used_key = await session.get(ClientRegistrationKey, second_registration_key.id)
        assert len(remote_clients) == 1
        assert remote_clients[0].hostname == "new-host"
        assert str(first_used_key.used_client_id) == first_body["client_id"]
        assert str(second_used_key.used_client_id) == first_body["client_id"]


@pytest.mark.asyncio
async def test_direct_client_registration_inherits_registration_key_owner(db_client):
    async with db_client.session_factory() as session:
        registration_key, key = await create_registration_key(
            session,
            label="desk",
            owner_user_id="alice",
        )
        await session.commit()

    response = await db_client.post(
        "/api/clients/register",
        json={
            "registration_key": key,
            "name": "Alice Direct Dev",
            "hostname": "direct-host",
            "install_path": "/home/alice/.web-terminal-acp",
            "server_url": "https://control.example.com",
        },
    )

    assert response.status_code == 200
    async with db_client.session_factory() as session:
        used_key = await session.get(ClientRegistrationKey, registration_key.id)
        client = await session.get(Client, UUID(response.json()["client_id"]))
        assert used_key.owner_user_id == "alice"
        assert client.owner_user_id == "alice"

@pytest.mark.asyncio
async def test_create_registration_key_returns_plain_key_once(db_client):
    response = await db_client.post("/api/clients/registration-keys", json={"label": "desk"})

    assert response.status_code == 200
    body = response.json()
    assert body["key"].startswith("wtr_")
    assert body["label"] == "desk"
    assert body["created_at"] is not None

@pytest.mark.asyncio
async def test_read_registration_script_returns_direct_client_installer(db_client):
    response = await db_client.get("/api/clients/register-script")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/x-shellscript")
    assert "WEB_TERMINAL_REGISTRATION_KEY" in response.text
    assert "/api/clients/register" in response.text
    assert "import shutil" in response.text
    assert "shutil.rmtree(app_root)" in response.text
    assert "refusing to replace unsafe app root" in response.text
    assert "raw.githubusercontent.com" not in response.text
    expected_script = (REPO_ROOT / "scripts/register-client-direct.sh").read_text(
        encoding="utf-8"
    )
    assert response.text == expected_script
