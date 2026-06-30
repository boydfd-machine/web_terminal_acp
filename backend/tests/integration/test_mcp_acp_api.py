from tests.integration.test_window_api_support import *
from pathlib import Path
from uuid import uuid4

from app.contexts.mcp_acp.api import routes as mcp_routes
from app.contexts.windows.application import window_creation as window_creation_service
from app.models import AiSession, ProjectTodo, WindowStatus
from app.repositories.clients import create_client


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
async def test_mcp_list_clients_and_windows_requires_valid_source(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)

    missing_source = await db_client.get("/api/mcp/acp/clients")
    clients = await db_client.get(
        "/api/mcp/acp/clients",
        headers=_source_headers(client_id, source_window_id),
    )
    windows = await db_client.get(
        f"/api/mcp/acp/clients/{client_id}/windows",
        headers=_source_headers(client_id, source_window_id),
    )

    assert missing_source.status_code == 401
    assert clients.status_code == 200
    assert clients.json()["clients"][0]["id"] == client_id
    assert clients.json()["clients"][0]["online"] is True
    assert windows.status_code == 200
    assert {window["id"] for window in windows.json()["windows"]} == {source_window_id}

@pytest.mark.asyncio
async def test_mcp_create_window_records_source_context(
    db_client: DbClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_id, source_window_id = await _create_source_window(db_client)

    monkeypatch.setattr(FakeTmuxManager, "server_url", "https://control.example.com", raising=False)
    monkeypatch.setattr(mcp_routes, "get_tmux_manager", FakeTmuxManager)
    monkeypatch.setattr(
        window_creation_service,
        "schedule_local_window_runtime_start",
        lambda **_kwargs: None,
    )

    response = await db_client.post(
        "/api/mcp/acp/windows",
        headers=_source_headers(client_id, source_window_id),
        json={
            "target_client_id": client_id,
            "cwd": "/workspace/remote-task",
            "shell_command": "/bin/bash",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["client_id"] == client_id
    assert body["derived_mode"] == "mcp_acp"
    assert body["derived_context"] == {
        "source_client_id": client_id,
        "source_window_id": source_window_id,
        "dispatch_depth": 1,
    }

    async with db_client.session_factory() as session:
        created = await session.get(VirtualWindow, UUID(body["id"]))
        assert created is not None
        assert created.derived_mode == "mcp_acp"
        assert created.derived_context["source_window_id"] == source_window_id

@pytest.mark.asyncio
async def test_agent_ops_create_local_window_ignores_broken_user_skill_symlink(
    db_client: DbClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    codex_home = tmp_path / ".codex"
    _write_skill(codex_home / "skills", "docker")
    (codex_home / "skills" / "missing-skill").symlink_to(tmp_path / "deleted-source")

    monkeypatch.setattr(mcp_routes, "get_tmux_manager", FakeTmuxManager)
    monkeypatch.setattr(
        window_creation_service,
        "schedule_local_window_runtime_start",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        window_creation_service.agent_config_service.Path,
        "home",
        lambda: tmp_path,
    )

    response = await db_client.post(
        "/api/agent-ops/windows",
        headers=_source_headers(client_id, source_window_id),
        json={
            "target_client_id": client_id,
            "cwd": "/workspace/local-task",
            "shell_command": "/bin/bash",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["client_id"] == client_id
    assert body["runtime_ready"] is False

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / body["id"]
    assert (managed / "skills" / "docker" / "SKILL.md").is_file()
    assert not (managed / "skills" / "missing-skill").exists()
    assert not (managed / "skills" / "missing-skill").is_symlink()

@pytest.mark.asyncio
async def test_agent_ops_capture_unready_runtime_returns_service_error(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    async with db_client.session_factory() as session:
        target = await create_window(
            session,
            UUID(client_id),
            cwd="/workspace/unready",
            shell_command="/bin/bash",
        )
        target.status = WindowStatus.error
        target_id = str(target.id)
        await session.commit()

    response = await db_client.post(
        "/api/agent-ops/windows/capture",
        headers=_source_headers(client_id, source_window_id),
        json={
            "target_client_id": client_id,
            "window_id": target_id,
            "history_lines": 10,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "terminal runtime is not ready"

@pytest.mark.asyncio
async def test_mcp_read_project_todo_returns_card_context(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": "/workspace/project"},
        json={"title": "Business card", "description": "Original requirement"},
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
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.assigned_window_id = work_window_id
        todo.assigned_agent = "codex"
        todo.dispatch_prompt = "Implement the business card"
        todo.dispatch_stage = "FAILED"
        todo.dispatch_error = "project todo dispatch waited for the agent-client prompt, but it was not ready"
        todo.implementation_worktree_json = {
            "worktree_root": "/workspace/project/.worktrees/business-card",
            "branch": "agent/business-card",
            "commits": [{"sha": "abc123", "subject": "Implement card"}],
            "files": [{"path": "backend/app.py", "status": "modified"}],
        }
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=work_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload("first instruction"),
                    fingerprint="mcp-card-context-user-1",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=work_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload("intermediate output"),
                    fingerprint="mcp-card-context-agent-1",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=work_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload("last output"),
                    fingerprint="mcp-card-context-agent-2",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
                GitWorktreeRun(
                    client_id=UUID(client_id),
                    virtual_window_id=work_window_id,
                    command_sequence="worktree:context",
                    status="completed",
                    worktree_root="/workspace/project/.worktrees/business-card",
                    main_repo_root="/workspace/project",
                    end_snapshot_json={"branch": "agent/business-card"},
                    session_diff_json={
                        "has_changes": True,
                        "commits": [{"sha": "abc123", "subject": "Implement card"}],
                        "files": [{"path": "backend/app.py", "status": "modified"}],
                    },
                ),
            ]
        )
        await session.commit()

    response = await db_client.post(
        "/api/mcp/acp/project-todos/read",
        headers=_source_headers(client_id, source_window_id),
        json={"todo_id": todo_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["todo"] | {
        "id": todo_id,
        "title": "Business card",
        "description": "Original requirement",
        "dispatch_prompt": "Implement the business card",
        "dispatch_stage": "FAILED",
        "dispatch_error": "project todo dispatch waited for the agent-client prompt, but it was not ready",
    } == body["todo"]
    assert body["worktree"]["commits"][0]["subject"] == "Implement card"
    assert body["agent_records"] == [
        {
            "role": "implementation",
            "window_id": str(work_window_id),
            "turns": [
                {
                    "user_input": "first instruction",
                    "user_created_at": body["agent_records"][0]["turns"][0]["user_created_at"],
                    "last_agent_output": "last output",
                    "last_agent_created_at": body["agent_records"][0]["turns"][0]["last_agent_created_at"],
                }
            ],
        }
    ]

@pytest.mark.asyncio
async def test_mcp_read_project_todo_is_scoped_to_source_client(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    async with db_client.session_factory() as session:
        other_client, _token = await create_client(session, name=f"Remote {uuid4()}")
        await session.commit()

    create_response = await db_client.post(
        f"/api/clients/{other_client.id}/projects/todos",
        params={"project_path": "/workspace/remote-project"},
        json={"title": "Remote card", "description": "Should not be readable from local source"},
    )
    assert create_response.status_code == 200

    response = await db_client.post(
        "/api/mcp/acp/project-todos/read",
        headers=_source_headers(client_id, source_window_id),
        json={"todo_id": create_response.json()["id"]},
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_agent_ops_search_project_todos_filters_to_source_client_and_project(db_client: DbClient) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    async with db_client.session_factory() as session:
        other_client, _token = await create_client(session, name=f"Remote {uuid4()}")
        session.add_all(
            [
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/workspace/alpha",
                    title="Ops search card alpha",
                    description="Find this card",
                    sort_order=1,
                ),
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/workspace/beta",
                    title="Ops search card beta",
                    description="Find this card",
                    sort_order=2,
                ),
                ProjectTodo(
                    client_id=other_client.id,
                    project_path="/workspace/beta",
                    title="Ops search card remote",
                    description="Find this card",
                    sort_order=3,
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        "/api/agent-ops/project-todos/search",
        headers=_source_headers(client_id, source_window_id),
        params={"q": "ops search", "project_path": "/workspace/beta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Ops search card beta"
    assert body["results"][0]["project_path"] == "/workspace/beta"
