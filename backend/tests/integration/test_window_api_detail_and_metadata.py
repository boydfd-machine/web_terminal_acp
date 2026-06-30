from tests.integration.test_window_api_support import *

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "remote_exc",
    [ClientConnectionClosed("client disconnected"), asyncio.TimeoutError()],
)
async def test_create_window_marks_remote_window_disconnected_when_runtime_create_becomes_unavailable(
    db_client, remote_exc
):
    remote_client_id = await create_remote_client_id(db_client)
    connection = FailingRemoteConnection(remote_exc)
    connection.request_continue.set()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )

    assert response.status_code == 200
    created = response.json()
    assert FakeTmuxManager.killed_targets == []

    persisted = await wait_for_remote_window_status(db_client, created["id"], "DISCONNECTED")
    assert persisted.remote_session_id is None
    assert persisted.remote_window_id is None

@pytest.mark.asyncio
async def test_create_window_marks_remote_window_error_when_runtime_reports_terminal_error(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = TerminalErrorRemoteConnection()
    connection.request_continue.set()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )

    assert response.status_code == 200
    created = response.json()

    persisted = await wait_for_remote_window_status(db_client, created["id"], "ERROR")
    assert persisted.remote_session_id is None
    assert persisted.remote_window_id is None

@pytest.mark.asyncio
async def test_get_window_returns_window_metadata(db_client):
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp/project", "shell_command": "/bin/zsh"}
    )
    created = create_response.json()

    get_response = await db_client.get(f"/api/clients/{client_id}/windows/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]
    assert get_response.json()["client_id"] == client_id
    assert get_response.json()["cwd"] == "/tmp/project"
    assert get_response.json()["shell_command"] == "/bin/zsh"
    assert get_response.json()["created_at"] == created["created_at"]
    assert get_response.json()["last_terminal_command_at"] is None
    assert get_response.json()["last_agent_event_at"] is None
    assert parse_response_datetime(get_response.json()["last_active_at"]) == parse_response_datetime(
        created["created_at"]
    )

@pytest.mark.asyncio
async def test_get_window_returns_overview_timestamps(db_client):
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp/project", "shell_command": "/bin/bash"}
    )
    window_id = UUID(create_response.json()["id"])
    created_at = datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc)
    command_at = created_at + timedelta(minutes=5)
    agent_at = created_at + timedelta(minutes=9)
    output_at = created_at + timedelta(minutes=10)
    recent_at = created_at + timedelta(minutes=12)

    async with db_client.session_factory() as session:
        window = await session.get(VirtualWindow, window_id)
        assert window is not None
        window.created_at = created_at
        window.terminal_last_output_at = output_at
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": "pytest", "sequence": 1},
                    fingerprint=f"test-command:{window_id}",
                    created_at=command_at,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    payload_json=codex_message_payload("done"),
                    fingerprint=f"test-agent:{window_id}",
                    created_at=agent_at,
                ),
                TerminalRecentUsage(
                    client_id=UUID(client_id),
                    window_id=window_id,
                    title="Terminal selected",
                    last_used_at=recent_at,
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    body = response.json()
    assert parse_response_datetime(body["created_at"]) == created_at
    assert parse_response_datetime(body["last_terminal_command_at"]) == command_at
    assert parse_response_datetime(body["last_agent_event_at"]) == agent_at
    assert parse_response_datetime(body["last_active_at"]) == recent_at


@pytest.mark.asyncio
async def test_get_window_returns_agent_token_usage(db_client):
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp/project", "shell_command": "codex"}
    )
    window_id = UUID(create_response.json()["id"])
    used_at = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="event_msg",
                virtual_window_id=window_id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 40,
                                "output_tokens": 12,
                                "reasoning_output_tokens": 3,
                                "total_tokens": 112,
                            },
                            "last_token_usage": {
                                "input_tokens": 80,
                                "cached_input_tokens": 30,
                                "output_tokens": 10,
                                "reasoning_output_tokens": 2,
                                "total_tokens": 90,
                            },
                            "model_context_window": 258400,
                        },
                    },
                },
                fingerprint=f"test-token-usage:{window_id}",
                created_at=used_at,
            )
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    usage = response.json()["agent_token_usage"]
    assert usage["context"]["total_tokens"] == 90
    assert usage["total"]["total_tokens"] == 112
    assert usage["total"]["cached_input_tokens"] == 40
    assert usage["total"]["reasoning_output_tokens"] == 3
    assert usage["context_window"] == 258400
    assert usage["providers"] == ["codex"]
    assert usage["event_count"] == 1

    record_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/detail"
    )

    assert record_response.status_code == 200
    assert record_response.json()["events"] == []


@pytest.mark.asyncio
async def test_move_window_to_folder(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    folder_response = await db_client.post(
        f"/api/clients/{client_id}/folders", json={"path": "/2026-05/生产排障"}
    )

    move_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"folder_id": folder_response.json()["id"], "title": "[Claude] 修复 Nginx 403"},
    )
    assert move_response.status_code == 200
    assert move_response.json()["title"] == "[Claude] 修复 Nginx 403"
    assert move_response.json()["folder_id"] == folder_response.json()["id"]

@pytest.mark.asyncio
async def test_patch_window_title_and_folder_set_manual_lock_flags(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    folder_response = await db_client.post(
        f"/api/clients/{client_id}/folders", json={"path": "/manual/folder"}
    )

    title_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"title": "Manual title"},
    )
    folder_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"folder_id": folder_response.json()["id"]},
    )

    assert title_response.status_code == 200
    assert title_response.json()["title_manually_overridden"] is True
    assert title_response.json()["folder_manually_overridden"] is False
    assert folder_response.status_code == 200
    assert folder_response.json()["title_manually_overridden"] is True
    assert folder_response.json()["folder_manually_overridden"] is True

@pytest.mark.asyncio
async def test_patch_window_summary_and_tags_do_not_set_manual_lock_flags(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"summary": "Reviewed by user.", "title_tags": ["reviewed"]},
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["title_manually_overridden"] is False
    assert patch_response.json()["folder_manually_overridden"] is False

@pytest.mark.asyncio
async def test_patch_window_records_title_history_with_summary_snapshot(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]

    summary_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}",
        json={"summary": "First summary."},
    )
    title_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}",
        json={"title": "Manual title"},
    )
    history_response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/title-history"
    )

    assert summary_response.status_code == 200
    assert title_response.status_code == 200
    assert history_response.status_code == 200
    body = history_response.json()
    assert body["total"] == 3
    assert body["has_more"] is False
    assert [(item["title"], item["summary"], item["source"]) for item in body["items"]] == [
        ("Manual title", "First summary.", "manual"),
        (window_response.json()["title"], "First summary.", "manual"),
        (window_response.json()["title"], None, "initial"),
    ]

@pytest.mark.asyncio
async def test_title_history_endpoint_is_client_scoped(db_client):
    local_client_id = await get_local_client_id(db_client)
    remote_client_id = await create_remote_client_id(db_client)
    async with db_client.session_factory() as session:
        remote_window = await create_window(session, UUID(remote_client_id), cwd="/tmp", shell_command="/bin/bash")
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{local_client_id}/windows/{remote_window.id}/title-history"
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_move_window_rejects_folder_from_another_client(db_client):
    local_client_id = await get_local_client_id(db_client)
    remote_client_id = await create_remote_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{local_client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    remote_folder_response = await db_client.post(
        f"/api/clients/{remote_client_id}/folders", json={"path": "/remote-only"}
    )

    move_response = await db_client.patch(
        f"/api/clients/{local_client_id}/windows/{window_response.json()['id']}",
        json={"folder_id": remote_folder_response.json()["id"]},
    )

    assert move_response.status_code == 404
    assert move_response.json() == {"detail": "folder not found"}

@pytest.mark.asyncio
async def test_delete_window_kills_tmux_and_archives_record(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]
    await wait_for_local_window_ready(db_client, client_id, window_id)

    delete_response = await db_client.delete(f"/api/clients/{client_id}/windows/{window_id}")

    assert delete_response.status_code == 204
    assert len(FakeTmuxManager.killed_targets) == 1
    assert FakeTmuxManager.killed_targets[0].session == "test_pool"
    assert FakeTmuxManager.killed_targets[0].window_id == "@99"

    get_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert get_response.status_code == 404

    async with db_client.session_factory() as session:
        archived_window = await session.get(VirtualWindow, UUID(window_id))
        assert archived_window is not None
        assert archived_window.status.value == "ARCHIVED"
        assert archived_window.archived_at is not None
        assert archived_window.folder_id is None
        assert archived_window.tmux_session is None
        assert archived_window.tmux_window_id is None

    tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    assert tree_response.status_code == 200
    tree_window_ids = [
        window["id"]
        for folder in tree_response.json()
        for window in folder["windows"]
    ]
    assert window_id not in tree_window_ids

@pytest.mark.asyncio
async def test_delete_pending_window_kills_tmux_after_runtime_start_finishes(db_client):
    client_id = await get_local_client_id(db_client)
    app.dependency_overrides[get_tmux_manager] = SlowTmuxManager
    SlowTmuxManager.create_started = asyncio.Event()
    SlowTmuxManager.create_continue = asyncio.Event()

    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]
    await asyncio.wait_for(SlowTmuxManager.create_started.wait(), timeout=1.0)

    delete_response = await db_client.delete(f"/api/clients/{client_id}/windows/{window_id}")
    assert delete_response.status_code == 204
    assert FakeTmuxManager.killed_targets == []

    SlowTmuxManager.create_continue.set()
    await wait_for_tmux_kill_count(1)
    assert FakeTmuxManager.killed_targets[0].session == "test_pool"
    assert FakeTmuxManager.killed_targets[0].window_id == "@99"

    get_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_last_window_removes_empty_topic_branch_and_summary_jobs(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "shell_command": "/bin/bash",
            "folder_path": "/开发调试/后端摘要",
        },
    )
    window_id = window_response.json()["id"]
    cached_tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    assert cached_tree_response.status_code == 200
    assert _tree_contains_path(cached_tree_response.json(), "/开发调试/后端摘要")

    async with db_client.session_factory() as session:
        session.add(
            SummaryJob(
                virtual_window_id=UUID(window_id),
                status=SummaryJobStatus.pending,
            )
        )
        await session.commit()

    delete_response = await db_client.delete(f"/api/clients/{client_id}/windows/{window_id}")

    assert delete_response.status_code == 204

    async with db_client.session_factory() as session:
        archived_window = await session.get(VirtualWindow, UUID(window_id))
        assert archived_window is not None
        assert archived_window.status.value == "ARCHIVED"
        assert archived_window.archived_at is not None
        assert archived_window.folder_id is None
        summary_jobs = list(await session.scalars(select(SummaryJob)))
        folders = list(await session.scalars(select(Folder).order_by(Folder.path)))

    assert summary_jobs == []
    assert "/开发调试" not in [folder.path for folder in folders]
    assert "/开发调试/后端摘要" not in [folder.path for folder in folders]

    tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    assert tree_response.status_code == 200
    assert not _tree_contains_path(tree_response.json(), "/开发调试")
    assert not _tree_contains_path(tree_response.json(), "/开发调试/后端摘要")

@pytest.mark.asyncio
async def test_delete_window_keeps_topic_when_another_terminal_remains(db_client):
    client_id = await get_local_client_id(db_client)
    first_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/first",
            "shell_command": "/bin/bash",
            "folder_path": "/开发调试/后端摘要",
        },
    )
    second_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/second",
            "shell_command": "/bin/bash",
            "folder_path": "/开发调试/后端摘要",
        },
    )

    delete_response = await db_client.delete(
        f"/api/clients/{client_id}/windows/{first_response.json()['id']}"
    )

    assert delete_response.status_code == 204

    tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    tree = tree_response.json()

    def find_folder(nodes, path):
        for node in nodes:
            if node["path"] == path:
                return node
            child = find_folder(node["folders"], path)
            if child is not None:
                return child
        return None

    target_folder = find_folder(tree, "/开发调试/后端摘要")
    assert target_folder is not None
    assert [window["id"] for window in target_folder["windows"]] == [second_response.json()["id"]]

@pytest.mark.asyncio
async def test_delete_window_returns_404_for_missing_window(db_client):
    client_id = await get_local_client_id(db_client)
    missing_window_id = "00000000-0000-4000-8000-000000000099"

    delete_response = await db_client.delete(f"/api/clients/{client_id}/windows/{missing_window_id}")

    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "window not found"}
