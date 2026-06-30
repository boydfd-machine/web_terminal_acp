from tests.integration.test_window_api_support import *
from app.contexts.windows.api import window_lifecycle_routes

@pytest.mark.asyncio
async def test_get_window_expired_cache_serves_stale_response(db_client, monkeypatch):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )
    window_id = window_response.json()["id"]

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert first_response.status_code == 200
    refreshes = []

    async def fail_get_window_for_client(_session, _client_id, _window_id):
        raise AssertionError("expired window cache should return stale before refresh")

    monkeypatch.setattr(polling_response_cache, "_CACHE_TTL_SECONDS", -1.0)
    monkeypatch.setattr(window_lifecycle_routes, "get_window_for_client", fail_get_window_for_client)
    monkeypatch.setattr(
        window_lifecycle_routes,
        "_refresh_window_response_cache",
        lambda cache_key, client_id, window_id, **_kwargs: refreshes.append(cache_key),
    )

    second_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert refreshes

@pytest.mark.asyncio
async def test_create_window_invalidates_activity_hot_cache(db_client):
    client_id = await get_local_client_id(db_client)
    cached_empty_activity = await db_client.get(f"/api/clients/{client_id}/windows/activity")
    assert cached_empty_activity.status_code == 200
    assert cached_empty_activity.json() == {"windows": []}

    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )
    assert create_response.status_code == 200

    activity_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert activity_response.status_code == 200
    assert [
        item["window_id"] for item in activity_response.json()["windows"]
    ] == [create_response.json()["id"]]

@pytest.mark.asyncio
async def test_windows_activity_does_not_scan_agent_records_for_git_worktree_marker(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "type": "function_call_output",
                    "output": f"Registered worktree\n{worktree_marker(window.id)}",
                },
                fingerprint=f"agent_tool_record:{window.id}:worktree-marker",
            )
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window.get("git_worktree") is None
    async with db_client.session_factory() as session:
        binding = await session.scalar(
            select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == UUID(window_id))
        )
        runs = list(
            await session.scalars(
                select(GitWorktreeRun).where(GitWorktreeRun.virtual_window_id == UUID(window_id))
            )
        )
    assert binding is None
    assert runs == []

@pytest.mark.asyncio
async def test_window_git_runs_materializes_git_worktree_from_agent_record_marker(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-2",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "payload": {
                        "type": "function_call_output",
                        "output": f"Registered worktree\n{worktree_marker(window.id)}",
                    },
                },
                fingerprint=f"agent_tool_record:{window.id}:worktree-git-runs",
            )
        )
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/git-runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["supported"] is True
    assert payload["total"] == 1
    assert payload["runs"][0]["run_type"] == "tracking"
    assert payload["runs"][0]["worktree_root"] == "/repo/.worktrees/feature"
    assert payload["runs"][0]["main_repo_root"] == "/repo"
    assert payload["runs"][0]["discovery_method"] == "osc"

@pytest.mark.asyncio
async def test_read_window_materializes_git_worktree_from_agent_record_marker(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-3",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "payload": {
                        "type": "function_call_output",
                        "output": f"Registered worktree\n{worktree_marker(window.id)}",
                    },
                },
                fingerprint=f"agent_tool_record:{window.id}:worktree-window-detail",
            )
        )
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    git_worktree = response.json()["git_worktree"]
    assert git_worktree["worktree_root"] == "/repo/.worktrees/feature"
    assert git_worktree["main_repo_root"] == "/repo"
    assert git_worktree["branch"] == "agent/feature"
    async with db_client.session_factory() as session:
        binding = await session.scalar(
            select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == window_id)
        )
    assert binding is not None

@pytest.mark.asyncio
async def test_expired_window_detail_cache_refresh_materializes_git_worktree_marker(
    db_client, monkeypatch
):
    monkeypatch.setattr(window_lifecycle_routes, "SessionLocal", db_client.session_factory)
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        window_id = window.id
        await session.commit()

    cached_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert cached_response.status_code == 200
    assert cached_response.json()["git_worktree"] is None

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-4",
                kind="response_item",
                virtual_window_id=window_id,
                payload_json={
                    "provider": "codex",
                    "payload": {
                        "type": "function_call_output",
                        "output": f"Registered worktree\n{worktree_marker(window_id)}",
                    },
                },
                fingerprint=f"agent_tool_record:{window_id}:worktree-window-cache-refresh",
            )
        )
        await session.commit()

    monkeypatch.setattr(polling_response_cache, "_CACHE_TTL_SECONDS", -1.0)

    stale_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert stale_response.status_code == 200
    assert stale_response.json()["git_worktree"] is None

    for _ in range(50):
        async with db_client.session_factory() as session:
            binding = await session.scalar(
                select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == window_id)
            )
        if binding is not None:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("expired window cache refresh did not materialize git binding")

    git_worktree = None
    for _ in range(50):
        refreshed_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
        assert refreshed_response.status_code == 200
        git_worktree = refreshed_response.json()["git_worktree"]
        if git_worktree is not None:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("refreshed window cache did not include git worktree")

    assert git_worktree["worktree_root"] == "/repo/.worktrees/feature"
    assert git_worktree["main_repo_root"] == "/repo"
    assert git_worktree["branch"] == "agent/feature"

@pytest.mark.asyncio
async def test_window_git_runs_returns_commit_file_diff_payload(db_client):
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
                branch="agent/feature",
                discovery_method="osc",
            )
        )
        session.add(
                GitWorktreeRun(
                    client_id=client.id,
                    virtual_window_id=window.id,
                    command_sequence=tracking_sequence("/repo/.worktrees/feature"),
                status="completed",
                main_repo_root="/repo",
                worktree_root="/repo/.worktrees/feature",
                discovery_method="osc",
                start_snapshot_json={"head_sha": "base"},
                end_snapshot_json={"head_sha": "feature"},
                session_diff_json={
                    "has_changes": True,
                    "head_moved": True,
                    "start_head": "base",
                    "end_head": "feature",
                    "commits": [
                        {
                            "sha": "feature",
                            "short_sha": "feature",
                            "subject": "Fix terminal reload autofocus reconnect",
                            "author_name": "Open Claw",
                            "author_email": "open@example.com",
                            "authored_at": "2026-05-27T05:55:00+00:00",
                            "files": [
                                {
                                    "path": "frontend/src/components/TerminalPane.tsx",
                                    "old_path": None,
                                    "status": "modified",
                                    "additions": 12,
                                    "deletions": 4,
                                    "patch": "@@ -1 +1 @@\n-old\n+new\n",
                                }
                            ],
                        }
                    ],
                    "files": [
                        {
                            "path": "frontend/src/components/TerminalPane.tsx",
                            "old_path": None,
                            "status": "modified",
                            "additions": 12,
                            "deletions": 4,
                            "commits": ["feature"],
                        }
                    ],
                },
            )
        )
        window_id = window.id
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/git-runs")

    assert response.status_code == 200
    diff = response.json()["runs"][0]["session_diff_json"]
    assert diff["commits"][0]["subject"] == "Fix terminal reload autofocus reconnect"
    assert diff["commits"][0]["files"][0]["path"] == "frontend/src/components/TerminalPane.tsx"
    assert diff["commits"][0]["files"][0]["patch"] == "@@ -1 +1 @@\n-old\n+new\n"
    assert diff["files"][0]["commits"] == ["feature"]

@pytest.mark.asyncio
async def test_windows_activity_returns_work_status_for_windows(db_client):
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
                fingerprint=f"agent_tool_record:{window.id}:activity-user",
                created_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "raw_type": "event_msg", "payload": {"type": "agent_message", "message": "Working"}},
                fingerprint=f"agent_tool_record:{window.id}:recent",
                created_at=datetime.now(timezone.utc) - timedelta(seconds=5),
            ),
        ])
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "WORKING"

@pytest.mark.asyncio
async def test_windows_activity_ignores_old_agent_output_written_after_shell_exit(db_client):
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
                payload_json={"command": "codex exec 'done'", "sequence": 44},
                fingerprint=f"terminal_input_command:{window.id}:codex-old-output-activity",
                created_at=now - timedelta(seconds=80),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 44, "exit_status": 0},
                fingerprint=f"terminal_command_finished:{window.id}:codex-old-output-activity",
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
                fingerprint=f"agent_tool_record:{window.id}:codex-old-output-activity",
                created_at=now - timedelta(seconds=5),
            ),
        ])
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "RECENT_ACTIVE"
    assert activity_window["work_status"]["last_working_activity_at"] is None
    assert activity_window["last_agent_task_status"] is None

@pytest.mark.asyncio
async def test_windows_activity_returns_to_working_after_completion_in_same_running_session(db_client):
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
                payload_json={"command": "codex", "sequence": 45},
                fingerprint=f"terminal_input_command:{window.id}:codex-multi-turn",
                created_at=now - timedelta(minutes=3),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json=codex_completion_payload(timestamp=now - timedelta(seconds=40)),
                fingerprint=f"agent_tool_record:{window.id}:codex-first-turn-complete",
                created_at=now - timedelta(seconds=40),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_user_message_payload(
                    "second turn",
                    timestamp=now - timedelta(seconds=15),
                ),
                fingerprint=f"agent_tool_record:{window.id}:codex-second-turn-user",
                created_at=now - timedelta(seconds=15),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload(
                    "second turn started",
                    timestamp=now - timedelta(seconds=10),
                ),
                fingerprint=f"agent_tool_record:{window.id}:codex-second-turn-output",
                created_at=now - timedelta(seconds=10),
            ),
        ])
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "WORKING"
    assert activity_window["work_status"]["last_working_activity_at"] is not None
    assert activity_window["last_agent_task_status"] is None
