from tests.integration.test_window_api_support import *
from pathlib import Path
from uuid import uuid4

from app.contexts.mcp_acp.api import routes as mcp_routes
from app.contexts.windows.application import window_creation as window_creation_service
from app.models import AiSession, ProjectTodo, ProjectTodoArtifact, WindowStatus
from app.repositories.clients import create_client
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_succeeded
from tests.integration.test_artifact_plugin_previews_api import PREVIEW_PAYLOAD


async def _create_source_window(db_client: DbClient) -> tuple[str, str]:
    local_client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        source = await create_window(
            session,
            UUID(local_client_id),
            cwd="/workspace/source",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@1",
        )
        source_id = str(source.id)
        await session.commit()
    return local_client_id, source_id


def _source_headers(client_id: str, window_id: str) -> dict[str, str]:
    return {
        "X-Web-Terminal-Source-Client-Id": client_id,
        "X-Web-Terminal-Source-Window-Id": window_id,
    }


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

@pytest.mark.asyncio
async def test_agent_ops_reads_preview_artifacts_and_plugin_previews(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": "/workspace/project"},
        json={"title": "Inspect agent ops outputs", "description": "Read linked outputs"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    work_window_id = uuid4()
    base_time = datetime.now(timezone.utc)

    async with db_client.session_factory() as session:
        work_window = VirtualWindow(
            id=work_window_id,
            client_id=UUID(client_id),
            title="Todo implementation",
            cwd="/workspace/project",
            shell_command="codex",
        )
        session.add(work_window)
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-session",
            virtual_window_id=work_window_id,
        )
        session.add(ai_session)
        await session.flush()
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=work_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload("build the linked artifact"),
                    fingerprint="agent-ops-preview-user",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=work_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload("artifact is ready"),
                    fingerprint="agent-ops-preview-agent",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=work_window_id,
            source_window_id=work_window_id,
            artifact_kind="agent_trace_graph",
            title="Linked trace",
        )
        await mark_artifact_succeeded(
            session,
            artifact,
            content_json={"title": "Linked trace", "nodes": []},
            display_html="<html><body>Linked trace</body></html>",
            metadata_json={"purpose": "agent-ops-test"},
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        link = ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=work_window_id,
            purpose="todo_artifact",
        )
        session.add(link)
        await session.commit()
        artifact_id = str(artifact.id)
        link_id = str(link.id)

    headers = _source_headers(client_id, source_window_id)
    agent_preview = await db_client.get(
        f"/api/agent-ops/clients/{client_id}/windows/{work_window_id}/agent-preview",
        headers=headers,
    )
    artifact_read = await db_client.get(
        f"/api/agent-ops/clients/{client_id}/windows/{work_window_id}/artifacts/{artifact_id}",
        headers=headers,
    )
    card_artifact_read = await db_client.get(
        f"/api/agent-ops/project-todos/{todo_id}/artifacts/{link_id}",
        headers=headers,
    )
    card_artifact_html = await db_client.get(
        f"/api/agent-ops/project-todos/{todo_id}/artifacts/{link_id}/html",
        headers=headers,
    )
    preview_upsert = await db_client.post(
        "/api/agent-ops/artifact-plugin-previews/upsert",
        headers=headers,
        json={**PREVIEW_PAYLOAD, "title": "Agent ops preview"},
    )
    preview_id = preview_upsert.json()["id"]
    plugin_preview = await db_client.get(
        f"/api/agent-ops/artifact-plugin-previews/{preview_id}",
        headers=headers,
    )
    plugin_preview_html = await db_client.get(
        f"/api/agent-ops/artifact-plugin-previews/{preview_id}/html",
        headers=headers,
    )
    other_client_id, other_source_window_id = await _create_source_window(db_client)
    other_preview_read = await db_client.get(
        f"/api/agent-ops/artifact-plugin-previews/{preview_id}",
        headers=_source_headers(other_client_id, other_source_window_id),
    )

    assert agent_preview.status_code == 200
    assert [(item["role"], item["body"]) for item in agent_preview.json()["messages"]] == [
        ("user", "build the linked artifact"),
        ("agent", "artifact is ready"),
    ]
    assert artifact_read.status_code == 200
    assert artifact_read.json()["content_json"]["title"] == "Linked trace"
    assert card_artifact_read.status_code == 200
    assert card_artifact_read.json()["id"] == artifact_id
    assert card_artifact_html.status_code == 200
    assert "Linked trace" in card_artifact_html.text
    assert preview_upsert.status_code == 200
    assert plugin_preview.status_code == 200
    assert plugin_preview.json()["components_json"]["python_source"] == PREVIEW_PAYLOAD["python_source"]
    assert plugin_preview.json()["rendered_content_json"]["title"] == "Demo preview"
    assert plugin_preview_html.status_code == 200
    assert "<h1>Demo preview</h1>" in plugin_preview_html.text
    assert other_client_id == client_id
    assert other_preview_read.status_code == 404

@pytest.mark.asyncio
async def test_mcp_upserts_artifact_plugin_preview_for_source_window(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    preview_id = str(uuid4())

    response = await db_client.post(
        "/api/mcp/acp/artifact-plugin-previews/upsert",
        headers=_source_headers(client_id, source_window_id),
        json={
            **PREVIEW_PAYLOAD,
            "preview_id": preview_id,
            "title": "MCP preview",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == preview_id
    assert body["client_id"] == client_id
    assert body["window_id"] == source_window_id
    assert body["created_by_window_id"] == source_window_id
    assert body["status"] == "valid"
    assert body["draft_artifact_kind"] == "custom_report"
    assert body["rendered_content_json"]["title"] == "Demo preview"
    assert "display_html" not in body

    list_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{source_window_id}/artifact-plugin-previews"
    )
    assert list_response.status_code == 200
    assert [preview["id"] for preview in list_response.json()["previews"]] == [preview_id]
