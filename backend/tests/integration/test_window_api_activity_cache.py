from tests.integration.test_window_api_support import *
from app.contexts.windows.api import window_lifecycle_routes
from app.models import ProjectTodo

@pytest.mark.asyncio
async def test_get_window_returns_recent_active_for_recent_shell_command(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "pwd"},
                fingerprint=f"terminal_input_command:{window.id}:recent",
                created_at=datetime.now(timezone.utc) - timedelta(seconds=30),
            )
        )
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    work_status = response.json()["work_status"]
    assert work_status["state"] == "RECENT_ACTIVE"
    assert work_status["label"] == "Terminal 活跃"
    assert work_status["color"] == "green"
    assert work_status["last_activity_at"] is not None
    assert work_status["last_working_activity_at"] is None

@pytest.mark.asyncio
async def test_get_window_returns_working_for_recent_agent_activity(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add_all([
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'fix tests'", "sequence": 42},
                fingerprint=f"terminal_input_command:{window.id}:codex",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_user_message_payload("fix tests"),
                fingerprint=f"agent_tool_record:{window.id}:recent-user",
                created_at=datetime.now(timezone.utc) - timedelta(seconds=15),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint=f"agent_tool_record:{window.id}:recent",
                created_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            ),
        ])
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    work_status = response.json()["work_status"]
    assert work_status["state"] == "WORKING"
    assert work_status["label"] == "Agent 工作中"
    assert work_status["color"] == "orange"
    assert work_status["last_activity_at"] is not None
    assert work_status["last_working_activity_at"] is not None

@pytest.mark.asyncio
async def test_get_window_does_not_mark_empty_agent_launch_as_working(db_client):
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add_all(
            [
                Event(
                    client_id=client.id,
                    source_type=EventSourceType.terminal,
                    source_id=str(window.id),
                    kind="terminal_input_command",
                    virtual_window_id=window.id,
                    payload_json={"command": "codex", "sequence": 43},
                    fingerprint=f"terminal_input_command:{window.id}:empty-codex",
                    created_at=now - timedelta(seconds=30),
                ),
                Event(
                    client_id=client.id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="session_meta",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "session_meta",
                        "payload": {"id": "codex-session"},
                    },
                    fingerprint=f"agent_tool_record:{window.id}:empty-session-meta",
                    created_at=now - timedelta(seconds=10),
                ),
            ]
        )
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    work_status = response.json()["work_status"]
    assert work_status["state"] == "RECENT_ACTIVE"
    assert work_status["last_working_activity_at"] is None

@pytest.mark.asyncio
async def test_get_window_ignores_old_agent_output_written_after_shell_exit(db_client):
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add_all([
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'done'", "sequence": 43},
                fingerprint=f"terminal_input_command:{window.id}:codex-old-output",
                created_at=now - timedelta(seconds=80),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 43, "exit_status": 0},
                fingerprint=f"terminal_command_finished:{window.id}:codex-old-output",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload(
                    "old output inserted late",
                    timestamp=now - timedelta(seconds=40),
                ),
                fingerprint=f"agent_tool_record:{window.id}:codex-old-output",
                created_at=now - timedelta(seconds=5),
            ),
        ])
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    work_status = response.json()["work_status"]
    assert work_status["state"] == "RECENT_ACTIVE"
    assert work_status["label"] == "Terminal 活跃"
    assert work_status["last_activity_at"] is not None
    assert work_status["last_working_activity_at"] is None

@pytest.mark.asyncio
async def test_windows_activity_returns_git_worktree_activity_without_remote_probe(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            WindowGitBinding(
                client_id=client.id,
                virtual_window_id=window.id,
                main_repo_root="/repo",
                worktree_root="/repo/.worktrees/feature",
                branch="feature",
                discovery_method="command",
            )
        )
        session.add(
            GitWorktreeRun(
                client_id=client.id,
                virtual_window_id=window.id,
                command_sequence="1",
                status="completed",
                pending_commit=True,
            )
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["git_worktree"] == {
        "worktree_root": "/repo/.worktrees/feature",
        "main_repo_root": "/repo",
        "branch": "feature",
        "pending_commit": True,
        "merge_status": "unknown",
        "merge_status_reason": "snapshot_unavailable",
        "merged_to_main": None,
        "merge_attention_required": False,
        "main_branch": None,
        "main_head_sha": None,
        "main_merge_head_sha": None,
        "main_merge_in_progress": False,
        "main_merge_matches_worktree": None,
        "unmerged_files": [],
    }

@pytest.mark.asyncio
async def test_windows_activity_returns_assigned_project_todo_title(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            ProjectTodo(
                client_id=client.id,
                project_path="/tmp",
                title="Fix switcher subtitle",
                assigned_window_id=window.id,
            )
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["todo_title"] == "Fix switcher subtitle"

@pytest.mark.asyncio
async def test_windows_activity_range_filters_windows_by_recent_activity(db_client):
    client_id = await get_local_client_id(db_client)
    current = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        old_window = await create_window(session, client.id, cwd="/old", shell_command="/bin/bash")
        recent_output_window = await create_window(
            session,
            client.id,
            cwd="/recent-output",
            shell_command="/bin/bash",
        )
        recent_created_window = await create_window(
            session,
            client.id,
            cwd="/recent-created",
            shell_command="/bin/bash",
        )
        old_window.created_at = current - timedelta(days=20)
        old_window.updated_at = current
        recent_output_window.created_at = current - timedelta(days=20)
        recent_output_window.updated_at = current - timedelta(days=20)
        recent_output_window.terminal_last_output_at = current - timedelta(days=2)
        recent_created_window.created_at = current - timedelta(days=2)
        recent_created_window.updated_at = current - timedelta(days=2)
        expected_window_ids = {str(recent_output_window.id), str(recent_created_window.id)}
        old_window_id = str(old_window.id)
        await session.commit()

    week_response = await db_client.get(f"/api/clients/{client_id}/windows/activity?range=7d")
    all_response = await db_client.get(f"/api/clients/{client_id}/windows/activity?range=all")

    assert week_response.status_code == 200
    assert all_response.status_code == 200
    week_window_ids = {item["window_id"] for item in week_response.json()["windows"]}
    all_window_ids = {item["window_id"] for item in all_response.json()["windows"]}
    assert week_window_ids == expected_window_ids
    assert old_window_id in all_window_ids
    assert expected_window_ids.issubset(all_window_ids)

@pytest.mark.asyncio
async def test_windows_activity_hot_cache_skips_client_and_activity_queries(db_client, monkeypatch):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        await session.commit()

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")
    assert first_response.status_code == 200

    async def fail_require_client(self, _client_id, *, session=None):
        raise AssertionError("hot activity cache should avoid client lookup")

    async def fail_load_client_windows_activity(
        _session,
        _client_id,
        *,
        include_runtime_tags=False,
        visible_since=None,
        project_path=None,
    ):
        raise AssertionError("hot activity cache should avoid activity query")

    monkeypatch.setattr(folders_api_service.FolderApiService, "_require_client", fail_require_client)
    monkeypatch.setattr(
        folders_api_service,
        "load_client_windows_activity",
        fail_load_client_windows_activity,
    )

    second_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()

@pytest.mark.asyncio
async def test_windows_activity_expired_cache_serves_stale_response(db_client, monkeypatch):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        await session.commit()

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")
    assert first_response.status_code == 200
    refreshes = []

    async def fail_load_client_windows_activity(
        _session,
        _client_id,
        *,
        include_runtime_tags=False,
        visible_since=None,
        project_path=None,
    ):
        raise AssertionError("expired activity cache should return stale before refresh")

    monkeypatch.setattr(polling_response_cache, "_CACHE_TTL_SECONDS", -1.0)
    monkeypatch.setattr(
        folders_api_service,
        "load_client_windows_activity",
        fail_load_client_windows_activity,
    )
    monkeypatch.setattr(
        folders_api_service.FolderApiService,
        "_refresh_response_cache",
        lambda self, cache_key, refresh: refreshes.append(cache_key),
    )

    second_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert refreshes

@pytest.mark.asyncio
async def test_get_window_hot_cache_skips_detail_queries(db_client, monkeypatch):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )
    window_id = window_response.json()["id"]

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert first_response.status_code == 200

    async def fail_require_client(_session, _client_id):
        raise AssertionError("hot window cache should avoid client lookup")

    async def fail_get_window_for_client(_session, _client_id, _window_id):
        raise AssertionError("hot window cache should avoid window lookup")

    async def fail_get_latest_summary_job(_session, _window_id):
        raise AssertionError("hot window cache should avoid summary job lookup")

    async def fail_runtime_tags_for_window_out(_session, _window):
        raise AssertionError("hot window cache should avoid runtime tag lookup")

    async def fail_load_work_status(_session, _client_id, _window_id):
        raise AssertionError("hot window cache should avoid work status lookup")

    monkeypatch.setattr(window_lifecycle_routes, "_require_client", fail_require_client)
    monkeypatch.setattr(window_lifecycle_routes, "get_window_for_client", fail_get_window_for_client)
    monkeypatch.setattr(window_lifecycle_routes, "get_latest_summary_job", fail_get_latest_summary_job)
    monkeypatch.setattr(window_lifecycle_routes, "runtime_tags_for_window_out", fail_runtime_tags_for_window_out)
    monkeypatch.setattr(window_lifecycle_routes, "load_work_status", fail_load_work_status)

    second_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()

@pytest.mark.asyncio
async def test_record_terminal_recent_invalidates_window_hot_cache(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )
    window_id = window_response.json()["id"]

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert first_response.status_code == 200

    recent_response = await db_client.post(
        f"/api/clients/{client_id}/terminal-recents",
        json={"window_id": window_id, "title": window_response.json()["title"]},
    )
    assert recent_response.status_code == 200

    second_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert second_response.status_code == 200
    assert parse_response_datetime(second_response.json()["last_active_at"]) >= parse_response_datetime(
        recent_response.json()["last_used_at"]
    )
    assert second_response.json()["last_active_at"] != first_response.json()["last_active_at"]
