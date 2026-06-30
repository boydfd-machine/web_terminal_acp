import pytest

from app.models import Client, ClientRuntime, ClientStatus
from tests.integration.test_agent_profiles_api import DbClient, db_client  # noqa: F401


@pytest.mark.asyncio
async def test_agent_profile_export_downloads_builtin_from_remote_client_route(
    db_client: DbClient,
) -> None:
    async with db_client.session_factory() as session:
        remote_client = Client(
            name="remote-laptop",
            status=ClientStatus.OFFLINE,
            token_hash="hash",
            runtime=ClientRuntime.remote,
        )
        session.add(remote_client)
        await session.commit()
        remote_client_id = remote_client.id

    export_response = await db_client.get(
        f"/api/clients/{remote_client_id}/agent-profiles/export",
        params={"profile_id": "builtin/developer"},
    )

    assert export_response.status_code == 200
    bundle = export_response.json()
    assert bundle["kind"] == "web-terminal-agent-profile"
    assert bundle["profile"]["id"] == "builtin/developer"
    assert {
        item["path"]
        for item in bundle["files"]["files"]
        if item["path"].startswith("skills/")
    } == {
        "skills/backend-development/SKILL.md",
        "skills/deep-research/SKILL.md",
        "skills/frontend-development/SKILL.md",
        "skills/tdd/SKILL.md",
    }
    assert export_response.headers["content-disposition"] == (
        'attachment; filename="builtin-developer.json"'
    )


@pytest.mark.asyncio
async def test_agent_profile_export_import_copies_builtin_as_editable_profile(
    db_client: DbClient,
) -> None:
    clients_response = await db_client.get("/api/clients")
    client_id = clients_response.json()[0]["id"]

    export_response = await db_client.get(
        f"/api/clients/{client_id}/agent-profiles/export",
        params={"profile_id": "builtin/developer"},
    )

    assert export_response.status_code == 200
    bundle = export_response.json()
    assert bundle["kind"] == "web-terminal-agent-profile"
    assert bundle["profile"]["id"] == "builtin/developer"
    assert any(
        item["path"] == "skills/frontend-development/SKILL.md"
        for item in bundle["files"]["files"]
    )

    import_response = await db_client.post(
        f"/api/clients/{client_id}/agent-profiles/import",
        json=bundle,
    )

    assert import_response.status_code == 200
    imported = import_response.json()
    assert imported["id"] != "builtin/developer"
    assert imported["name"] == "Developer"
    assert imported["agent_md"] == bundle["profile"]["agent_md"]

    update_response = await db_client.patch(
        f"/api/clients/{client_id}/agent-profiles/{imported['id']}",
        json={"name": "Imported Developer"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Imported Developer"

    config_response = await db_client.get(
        f"/api/clients/{client_id}/agent-profiles/{imported['id']}/agent-config/codex"
    )
    assert config_response.status_code == 200
    skills = next(section for section in config_response.json()["sections"] if section["id"] == "skills")
    skill_items = {item["id"]: item for item in skills["items"]}
    assert skill_items["frontend-development"]["enabled"] is True
    assert skill_items["backend-development"]["enabled"] is True
