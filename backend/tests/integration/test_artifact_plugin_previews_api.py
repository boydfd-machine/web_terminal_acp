from tests.integration.test_window_api_support import *
from uuid import uuid4

from app.models import TerminalArtifact


PREVIEW_PAYLOAD = {
    "title": "Custom report preview",
    "python_source": '''
ARTIFACT_KIND = "custom_report"
LABEL = "Custom Report"
DEFAULT_TITLE = "Custom report"
'''.strip(),
    "prompt_template": "Build {{ artifact_kind }} for {{ source_title }}.",
    "html_template": "<html><body><h1>{{ content.title }}</h1><p>{{ content.summary }}</p></body></html>",
    "json_schema": {
        "type": "object",
        "required": ["artifact_kind", "title", "summary"],
        "properties": {
            "artifact_kind": {"const": "custom_report"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "demo_content_json": {
        "artifact_kind": "custom_report",
        "title": "Demo preview",
        "summary": "Preview summary",
    },
}


@pytest.mark.asyncio
async def test_artifact_plugin_preview_api_renders_virtual_preview(db_client: DbClient) -> None:
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        window = await create_window(
            session,
            UUID(client_id),
            cwd="/workspace/project",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@1",
        )
        window_id = str(window.id)
        await session.commit()

    created = await db_client.post(
        "/api/artifact-plugin-previews",
        json={
            **PREVIEW_PAYLOAD,
            "client_id": client_id,
            "window_id": window_id,
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["client_id"] == client_id
    assert body["window_id"] == window_id
    assert body["created_by_window_id"] == window_id
    assert body["status"] == "valid"
    assert body["draft_artifact_kind"] == "custom_report"
    assert body["rendered_content_json"]["summary"] == "Preview summary"
    assert body["display_html"] is None

    list_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/artifact-plugin-previews"
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["previews"][0]["id"] == body["id"]
    assert listed["previews"][0]["display_html"] is None

    html_response = await db_client.get(f"/api/artifact-plugin-previews/{body['id']}/html")
    assert html_response.status_code == 200
    assert "<h1>Demo preview</h1>" in html_response.text

    async with db_client.session_factory() as session:
        artifacts = (await session.scalars(select(TerminalArtifact))).all()
        assert artifacts == []


@pytest.mark.asyncio
async def test_artifact_plugin_preview_api_persists_invalid_preview(db_client: DbClient) -> None:
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        window = await create_window(
            session,
            UUID(client_id),
            cwd="/workspace/project",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@1",
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.post(
        "/api/artifact-plugin-previews",
        json={
            **PREVIEW_PAYLOAD,
            "client_id": client_id,
            "window_id": window_id,
            "demo_content_json": {
                "artifact_kind": "custom_report",
                "title": "Missing summary",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "invalid"
    assert "'summary' is a required property" in body["last_error"]
    assert body["rendered_content_json"] is None

    html_response = await db_client.get(f"/api/artifact-plugin-previews/{body['id']}/html")
    assert html_response.status_code == 404
    assert "'summary' is a required property" in html_response.json()["detail"]


@pytest.mark.asyncio
async def test_artifact_plugin_preview_api_updates_stable_preview_session(db_client: DbClient) -> None:
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        window = await create_window(
            session,
            UUID(client_id),
            cwd="/workspace/project",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@1",
        )
        window_id = str(window.id)
        await session.commit()
    preview_id = str(uuid4())

    first = await db_client.put(
        f"/api/artifact-plugin-previews/{preview_id}",
        json={
            **PREVIEW_PAYLOAD,
            "client_id": client_id,
            "window_id": window_id,
        },
    )
    second = await db_client.put(
        f"/api/artifact-plugin-previews/{preview_id}",
        json={
            **PREVIEW_PAYLOAD,
            "client_id": client_id,
            "window_id": window_id,
            "title": "Renamed preview",
            "demo_content_json": {
                "artifact_kind": "custom_report",
                "title": "Updated preview",
                "summary": "Updated summary",
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == preview_id
    assert second.json()["title"] == "Renamed preview"
    assert second.json()["rendered_content_json"]["title"] == "Updated preview"

    list_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/artifact-plugin-previews"
    )
    assert [preview["id"] for preview in list_response.json()["previews"]] == [preview_id]
