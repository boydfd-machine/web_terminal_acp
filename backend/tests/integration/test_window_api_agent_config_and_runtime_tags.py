import io
from pathlib import Path
import shutil
import zipfile

from tests.integration.test_window_api_support import *


@pytest.mark.asyncio
async def test_delete_remote_window_requests_kill_when_client_is_online(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = FakeRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    delete_response = await db_client.delete(f"/api/clients/{remote_client_id}/windows/{window_id}")

    assert delete_response.status_code == 204
    assert len(connection.requests) == 2
    assert connection.requests[1].type == "kill_window"
    assert connection.requests[1].window_id == UUID(window_id)

    async with db_client.session_factory() as session:
        archived_window = await session.get(VirtualWindow, UUID(window_id))
        assert archived_window is not None
        assert archived_window.status.value == "ARCHIVED"
        assert archived_window.archived_at is not None
        assert archived_window.remote_session_id is None
        assert archived_window.remote_window_id is None

    get_response = await db_client.get(f"/api/clients/{remote_client_id}/windows/{window_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_patch_window_updates_metadata_fields(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={
            "title": "Reviewed terminal",
            "status": "ARCHIVED",
            "summary": "Nginx 403 was caused by a missing index file.",
            "title_tags": ["Claude", "Nginx"],
        },
    )

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["title"] == "Reviewed terminal"
    assert body["status"] == "ARCHIVED"
    assert body["summary"] == "Nginx 403 was caused by a missing index file."
    assert body["title_tags"] == ["Claude", "Nginx"]


@pytest.mark.asyncio
async def test_window_and_tree_include_runtime_tags_for_agent_and_path(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    assert window_response.status_code == 200
    assert window_response.json()["runtime_tags"] == ["/tmp/project"]
    window_id = window_response.json()["id"]

    async with db_client.session_factory() as session:
        window = await session.get(VirtualWindow, UUID(window_id))
        assert window is not None
        window.title_tags = ["summary", "nginx"]
        session.add(
            AiSession(
                client_id=UUID(client_id),
                provider="codex",
                source_id="codex-session-runtime-tags",
                project_path="/workspace/project",
                virtual_window_id=UUID(window_id),
            )
        )
        await session.commit()

    detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["runtime_tags"] == ["codex", "/workspace/project"]

    tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    assert tree_response.status_code == 200
    tree = tree_response.json()
    tree_window = next(
        window for folder in tree for window in folder["windows"] if window["id"] == window_id
    )
    assert "runtime_tags" not in tree_window
    assert "work_status" not in tree_window
    assert tree_window["title_tags"] == ["summary", "nginx"]

    activity_response = await db_client.get(
        f"/api/clients/{client_id}/windows/activity",
        params={"include_runtime_tags": "true"},
    )
    assert activity_response.status_code == 200
    activity_window = next(
        item for item in activity_response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["runtime_tags"] == ["codex", "/workspace/project"]


@pytest.mark.asyncio
async def test_create_local_window_resolves_agent_model_selection_from_database(db_client):
    client_id = await get_local_client_id(db_client)
    preset_response = await db_client.put(
        "/api/system-agent-config/model-presets/openai-main",
        json={
            "name": "OpenAI Main",
            "providers": ["openai_compatible"],
            "base_url": "https://models.example.com/v1",
            "api_key": "secret-key",
            "models": ["model-a", "model-b"],
            "model_configs": [
                {"name": "model-a", "max_output_tokens": 4096},
                {
                    "name": "model-b",
                    "max_output_tokens": 8192,
                    "context_window": 258400,
                    "auto_compact_token_limit": 200000,
                },
            ],
        },
    )
    assert preset_response.status_code == 200

    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "model_selection": {"preset_id": "openai-main", "model": "model-b"},
            },
        },
    )

    assert window_response.status_code == 200
    window_id = UUID(window_response.json()["id"])
    async with db_client.session_factory() as session:
        window = await session.get(VirtualWindow, window_id)
        assert window is not None
        assert window.derived_context == {
            "agent_model": {
                "preset_id": "openai-main",
                "provider": "openai_compatible",
                "model": "model-b",
                "max_output_tokens": 8192,
                "context_window": 258400,
                "auto_compact_token_limit": 200000,
            }
        }


@pytest.mark.asyncio
async def test_window_agent_config_exposes_and_updates_model(db_client, tmp_path, monkeypatch):
    monkeypatch.setattr(windows_router.agent_config_service.Path, "home", lambda: tmp_path)
    client_id = await get_local_client_id(db_client)
    await db_client.put(
        "/api/system-agent-config/model-presets/openai-main",
        json={
            "name": "OpenAI Main",
            "providers": ["openai_compatible"],
            "base_url": "https://models.example.com/v1",
            "api_key": "secret-key",
            "models": ["model-a", "model-b"],
        },
    )

    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "model_selection": {"preset_id": "openai-main", "model": "model-a"},
            },
        },
    )
    window_id = window_response.json()["id"]

    get_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-config"
    )
    assert get_response.status_code == 200
    model_view = get_response.json()["model"]
    assert model_view["editable"] is True
    assert model_view["provider"] == "codex"
    assert model_view["preset_id"] == "openai-main"
    assert model_view["model"] == "model-a"
    assert model_view["available_models"] == ["model-a", "model-b"]

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}/agent-config/model",
        json={"codex_model_reasoning_effort": "high"},
    )
    assert patch_response.status_code == 200
    updated_model = patch_response.json()["model"]
    assert updated_model["codex_model_reasoning_effort"] == "high"

    config_toml = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / window_id / "config.toml"
    ).read_text()
    assert 'model_reasoning_effort = "high"' in config_toml


@pytest.mark.asyncio
async def test_create_local_window_materializes_system_config_from_database(
    db_client,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(windows_router.agent_config_service.Path, "home", lambda: tmp_path)
    client_id = await get_local_client_id(db_client)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("review-helper/SKILL.md", "---\nname: Review Helper\n---\n")

    saved = await db_client.put(
        "/api/system-agent-config/skills/review-helper",
        content=archive_buffer.getvalue(),
        headers={"content-type": "application/zip"},
    )
    assert saved.status_code == 200
    shutil.rmtree(tmp_path / ".web-terminal-acp" / "system-config")

    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": {
                    "agent": "codex",
                    "sections": [
                        {"id": "skills", "items": [{"id": "review-helper", "enabled": True}]}
                    ],
                },
            },
        },
    )

    assert window_response.status_code == 200
    window_id = window_response.json()["id"]
    skill_file = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / window_id
        / "skills"
        / "review-helper"
        / "SKILL.md"
    )
    assert skill_file.read_text(encoding="utf-8") == "---\nname: Review Helper\n---\n"


@pytest.mark.asyncio
async def test_client_system_agent_config_endpoint_materializes_system_config_from_database(
    db_client,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client_id = await get_local_client_id(db_client)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fuck-shit-mountain/SKILL.md", "---\nname: fuck shit mountain\n---\n")

    saved = await db_client.put(
        "/api/system-agent-config/skills/fuck-shit-mountain",
        content=archive_buffer.getvalue(),
        headers={"content-type": "application/zip"},
    )
    assert saved.status_code == 200
    shutil.rmtree(tmp_path / ".web-terminal-acp" / "system-config")

    config_response = await db_client.get(f"/api/clients/{client_id}/system-agent-config")

    assert config_response.status_code == 200
    skills = next(section for section in config_response.json()["sections"] if section["id"] == "skills")
    system_skill = next(item for item in skills["items"] if item["id"] == "fuck-shit-mountain")
    assert system_skill["name"] == "fuck shit mountain"
    assert system_skill["enabled"] is True
    assert system_skill["origin"] == "system_config"


@pytest.mark.asyncio
async def test_terminal_projects_and_project_scoped_tree_use_runtime_project_path(db_client):
    client_id = await get_local_client_id(db_client)
    first_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/first", "shell_command": "/bin/bash"},
    )
    second_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/second", "shell_command": "/bin/bash"},
    )
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_window_id = first_response.json()["id"]

    async with db_client.session_factory() as session:
        session.add(
            AiSession(
                client_id=UUID(client_id),
                provider="codex",
                source_id="codex-project-first",
                project_path="/workspace/shared",
                virtual_window_id=UUID(first_window_id),
            )
        )
        await session.commit()

    projects_response = await db_client.get(f"/api/clients/{client_id}/terminal-projects")
    assert projects_response.status_code == 200
    assert projects_response.json() == [
        {"project_path": "/tmp/second", "window_count": 1},
        {"project_path": "/workspace/shared", "window_count": 1},
    ]

    tree_response = await db_client.get(
        f"/api/clients/{client_id}/tree",
        params={"project_path": "/workspace/shared"},
    )
    assert tree_response.status_code == 200
    tree_window_ids = {
        window["id"] for folder in tree_response.json() for window in folder["windows"]
    }
    assert tree_window_ids == {first_window_id}

    activity_response = await db_client.get(
        f"/api/clients/{client_id}/windows/activity",
        params={"include_runtime_tags": "true", "project_path": "/workspace/shared"},
    )
    assert activity_response.status_code == 200
    assert [item["window_id"] for item in activity_response.json()["windows"]] == [first_window_id]
    assert activity_response.json()["windows"][0]["runtime_tags"] == ["codex", "/workspace/shared"]


@pytest.mark.asyncio
async def test_get_window_agent_record_returns_sessions_and_non_output_events(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="claude",
            source_id="claude-session-1",
            source_path="/home/user/.claude/session.jsonl",
            virtual_window_id=window_id,
        )
        session.add(ai_session)
        await session.flush()
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.claude_jsonl,
                    source_id="claude-session-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={"type": "user", "message": {"content": "hello"}},
                    fingerprint="agent-record-user",
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": "codex", "shell": "bash"},
                    fingerprint="agent-record-command",
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_output",
                    virtual_window_id=window_id,
                    payload_json={"text": "raw terminal output"},
                    fingerprint="agent-record-output",
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record")

    assert response.status_code == 200
    body = response.json()
    assert body["window_id"] == str(window_id)
    assert [item["source_id"] for item in body["sessions"]] == ["claude-session-1"]
    assert [item["kind"] for item in body["events"]] == ["user_message", "terminal_input_command"]
    assert body["events"][0]["payload_json"]["message"]["content"] == "hello"
    assert (
        body["events"][0]["projection"]
        | {
            "tone": "user-input",
            "label": "User input",
            "body": "hello",
            "body_format": "markdown",
            "subtype": "user_message",
        }
        == body["events"][0]["projection"]
    )
    assert (
        body["events"][1]["projection"]
        | {
            "tone": "terminal",
            "label": "Terminal command",
            "body": "codex",
            "body_format": "markdown",
            "subtype": "command",
        }
        == body["events"][1]["projection"]
    )
    assert body["events_total"] == 2
    assert body["events_limit"] == 100
    assert body["events_offset"] == 0
    assert body["events_has_more"] is False
