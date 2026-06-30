import re

from tests.integration.test_window_api_support import *

@pytest.mark.asyncio
async def test_create_window_does_not_start_tmux_when_database_commit_fails(db_client, monkeypatch):
    client_id = await get_local_client_id(db_client)
    app.dependency_overrides[get_tmux_manager] = CommitFailingOnSecondCallTmuxManager
    CommitFailingOnSecondCallTmuxManager.commit_calls = 0
    original_commit = AsyncSession.commit

    async def fail_commit(self):
        CommitFailingOnSecondCallTmuxManager.commit_calls += 1
        if CommitFailingOnSecondCallTmuxManager.commit_calls >= 2:
            raise RuntimeError("commit failed")
        await original_commit(self)

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="commit failed"):
        await db_client.post(
            f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
        )

    assert CommitFailingOnSecondCallTmuxManager.killed_targets == []

@pytest.mark.asyncio
async def test_create_window_commits_client_lookup_before_tmux_create(db_client):
    client_id = await get_local_client_id(db_client)
    app.dependency_overrides[get_tmux_manager] = ObservingTmuxManager
    ObservingTmuxManager.observed_in_transaction = None

    async with db_client.session_factory() as session:
        windows_router._TEST_OBSERVED_SESSION = session
        try:
            response = await db_client.post(
                f"/api/clients/{client_id}/windows",
                json={"cwd": "/tmp", "shell_command": "/bin/bash"},
            )
            assert response.status_code == 200
            await wait_for_local_window_ready(db_client, client_id, response.json()["id"])
        finally:
            delattr(windows_router, "_TEST_OBSERVED_SESSION")

    assert ObservingTmuxManager.observed_in_transaction is False

@pytest.mark.asyncio
async def test_create_window_marks_window_error_when_tmux_create_is_cancelled(db_client):
    client_id = await get_local_client_id(db_client)
    client = windows_router._RuntimeClient(UUID(client_id), ClientRuntime.local)

    async with db_client.session_factory() as session:
        created = await windows_router._create_virtual_window_for_client(
            client,
            WindowCreateIn(cwd="/tmp", shell_command="/bin/bash"),
            session,
            CancellingTmuxManager(),
            session_factory=db_client.session_factory,
        )

    async with db_client.session_factory() as session:
        assert session.in_transaction() is False
    persisted = await wait_for_remote_window_status(db_client, str(created.id), "ERROR")
    assert persisted.tmux_session is None
    assert persisted.tmux_window_id is None

@pytest.mark.asyncio
async def test_create_window_with_folder_path_assigns_topic_folder(db_client):
    client_id = await get_local_client_id(db_client)
    response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "shell_command": "/bin/bash",
            "folder_path": "/开发调试/后端摘要",
        },
    )
    assert response.status_code == 200
    created = response.json()

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
    assert any(window["id"] == created["id"] for window in target_folder["windows"])
    assert created["folder_manually_overridden"] is True
    assert created["cwd"] == "/tmp/project"

@pytest.mark.asyncio
async def test_create_window_appears_in_uncategorized_tree(db_client):
    client_id = await get_local_client_id(db_client)
    response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    assert response.status_code == 200
    created = response.json()
    assert created["client_id"] == client_id
    assert re.match(r"^Terminal \d{2}/\d{2} \d{2}:\d{2}$", created["title"])
    assert created["status"] == "ACTIVE"
    assert created["tmux_session"] is None
    assert created["tmux_window_id"] is None
    assert created["remote_session_id"] is None
    assert created["remote_window_id"] is None
    assert created["title_manually_overridden"] is False
    assert created["folder_manually_overridden"] is False
    assert created["command_capture_supported"] is True
    assert created["summary_job"] is None
    persisted = await wait_for_local_window_ready(db_client, client_id, created["id"])
    assert persisted.tmux_session == "test_pool"
    assert persisted.tmux_window_id == "@99"
    assert persisted.tmux_window_index == "4"

    detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["tmux_window_index"] == "4"

    tree_response = await db_client.get(f"/api/clients/{client_id}/tree")
    tree = tree_response.json()
    uncategorized = next(folder for folder in tree if folder["path"] == "/未分类")
    assert uncategorized["windows"][0]["id"] == created["id"]
    assert uncategorized["windows"][0]["created_at"] == created["created_at"]

@pytest.mark.asyncio
async def test_create_window_persists_remote_session_and_window_ids(db_client):
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(
            session,
            client.id,
            cwd="/tmp",
            shell_command="/bin/bash",
            remote_session_id="remote-session-123",
            remote_window_id="remote-window-456",
        )
        window_id = window.id
        await session.commit()

    async with db_client.session_factory() as session:
        persisted = await session.get(VirtualWindow, window_id)

    assert persisted is not None
    assert persisted.remote_session_id == "remote-session-123"
    assert persisted.remote_window_id == "remote-window-456"

@pytest.mark.asyncio
async def test_read_window_backfills_existing_tmux_window_index(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        window = await create_window(
            session,
            UUID(client_id),
            cwd="/tmp",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@99",
        )
        window_id = window.id
        await session.commit()

    detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["tmux_window_index"] == "4"
    async with db_client.session_factory() as session:
        persisted = await session.get(VirtualWindow, window_id)
    assert persisted is not None
    assert persisted.tmux_window_index == "4"

@pytest.mark.asyncio
async def test_read_window_bypasses_cached_null_tmux_window_index(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        window = await create_window(
            session,
            UUID(client_id),
            cwd="/tmp",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@99",
        )
        window_id = window.id
        cache_key = (
            "window",
            polling_response_cache.response_cache_scope(session),
            UUID(client_id),
            window_id,
        )
        await session.commit()

    polling_response_cache.store_json_response(
        cache_key,
        {
            "tmux_session": "test_pool",
            "tmux_window_id": "@99",
            "tmux_window_index": None,
        },
        resources={"window"},
        client_id=UUID(client_id),
    )

    detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["tmux_window_index"] == "4"
    async with db_client.session_factory() as session:
        persisted = await session.get(VirtualWindow, window_id)
    assert persisted is not None
    assert persisted.tmux_window_index == "4"

@pytest.mark.asyncio
async def test_create_window_creates_remote_window_when_client_connection_exists(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp/ignored", "shell_command": "/bin/bash"},
    )

    assert response.status_code == 200
    created = response.json()
    await allow_remote_create_to_finish(connection)
    persisted = await wait_for_remote_window_ready(db_client, remote_client_id, created["id"])
    create_payload = connection.requests[0].payload
    create_payload.pop("agent_config_selection", None)
    assert create_payload.pop("system_config_files")["version"] == 1
    assert created["client_id"] == remote_client_id
    assert created["tmux_session"] is None
    assert created["tmux_window_id"] is None
    assert created["remote_session_id"] is None
    assert created["remote_window_id"] is None
    assert persisted.remote_session_id == "remote-session"
    assert persisted.remote_window_id == "remote-window"
    assert len(connection.requests) == 1
    assert connection.requests[0].type == "create_window"
    assert connection.requests[0].client_id == UUID(remote_client_id)
    assert connection.requests[0].window_id == UUID(created["id"])
    assert create_payload == {"cwd": "/tmp/ignored", "shell_command": "/bin/bash"}
    assert created["cwd"] == "/tmp/ignored"
    assert created["shell_command"] == "/bin/bash"
    assert persisted.cwd == "/tmp/ignored"
    assert persisted.shell_command == "/bin/bash"
    assert FakeTmuxManager.killed_targets == []

@pytest.mark.asyncio
async def test_read_agent_clients_returns_builtin_plugin_descriptors(db_client):
    client_id = await get_local_client_id(db_client)

    response = await db_client.get(f"/api/clients/{client_id}/agent-clients")

    assert response.status_code == 200
    clients = {item["id"]: item for item in response.json()["agent_clients"]}
    assert clients["codex"]["provider_id"] == "codex"
    assert clients["codex"]["capabilities"]["agent_records"] is True
    assert clients["claude"]["provider_id"] == "claude_code"
    assert clients["cursor"]["default_command"] == "agent"
    assert "cursor-agent" in clients["cursor"]["command_names"]

@pytest.mark.asyncio
async def test_read_agent_clients_queries_remote_client_descriptors(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = FakeRemoteConnection()
    connection.request_continue.set()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.get(f"/api/clients/{remote_client_id}/agent-clients")

    assert response.status_code == 200
    assert connection.requests[0].type == "agent_clients_list"
    clients = {item["id"]: item for item in response.json()["agent_clients"]}
    assert clients == {
        "remote_codex": {
            "id": "remote_codex",
            "provider_id": "codex",
            "label": "Remote Codex",
            "aliases": [],
            "default_command": "codex",
            "command_names": ["codex"],
            "capabilities": {},
        }
    }

@pytest.mark.asyncio
async def test_create_agent_window_sends_remote_config_selection(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)
    upload_response = await db_client.put(
        "/api/system-agent-config/skills/image-to-ppt",
        content=skill_zip_bytes("image-to-ppt", "---\nname: Image to PPT\n---\n"),
    )
    assert upload_response.status_code == 200

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {
                "agent": "claude",
                "command": "claude",
                "config": {
                    "agent": "claude",
                    "sections": [
                        {
                            "id": "skills",
                            "items": [{"id": "review", "enabled": True}],
                        }
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    created = response.json()
    await allow_remote_create_to_finish(connection)
    assert created["shell_command"] == "claude"
    assert created["command_capture_supported"] is True
    assert "claude_code" in created["runtime_tags"]
    assert [request.type for request in connection.requests[:2]] == ["agent_clients_list", "create_window"]
    create_payload = dict(connection.requests[1].payload)
    system_config_files = create_payload.pop("system_config_files")
    assert any(
        file["path"] == "skills/image-to-ppt/SKILL.md"
        for file in system_config_files["files"]
    )
    assert create_payload == {
        "cwd": "/tmp/project",
        "shell_command": "claude",
        "agent_config_selection": {
            "agent": "claude",
            "sections": [
                {
                    "id": "skills",
                    "items": [{"id": "review", "enabled": True}],
                }
            ],
        },
    }

@pytest.mark.asyncio
async def test_create_remote_agent_window_allows_remote_only_agent_descriptor(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = FutureAgentRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {
                "agent": "future_agent",
                "command": "future-agent",
                "config": {
                    "agent": "future_agent",
                    "sections": [
                        {
                            "id": "skills",
                            "items": [{"id": "review", "enabled": True}],
                        }
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    created = response.json()
    await allow_remote_create_to_finish(connection)
    assert created["shell_command"] == "future-agent"
    assert "future_provider" not in created["runtime_tags"]
    assert [request.type for request in connection.requests[:2]] == ["agent_clients_list", "create_window"]
    create_payload = dict(connection.requests[1].payload)
    create_payload.pop("system_config_files", None)
    assert create_payload == {
        "cwd": "/tmp/project",
        "shell_command": "future-agent",
        "agent_config_selection": {
            "agent": "future_agent",
            "sections": [
                {
                    "id": "skills",
                    "items": [{"id": "review", "enabled": True}],
                }
            ],
        },
    }

@pytest.mark.asyncio
async def test_create_remote_agent_window_rejects_launch_disabled_descriptor(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = CapabilityRemoteConnection({"launch": False})
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={
            "cwd": "/tmp/project",
            "agent_launch": {"agent": "restricted_agent", "command": "restricted-agent"},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "agent client does not support launch"
    assert [request.type for request in connection.requests] == ["agent_clients_list"]

@pytest.mark.asyncio
async def test_create_remote_window_returns_before_runtime_create_finishes(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp/slow", "shell_command": "/bin/bash"},
    )

    assert response.status_code == 200
    created = response.json()
    assert created["remote_session_id"] is None
    assert created["remote_window_id"] is None

    await allow_remote_create_to_finish(connection)
    persisted = await wait_for_remote_window_ready(db_client, remote_client_id, created["id"])
    assert persisted.remote_session_id == "remote-session"
    assert persisted.remote_window_id == "remote-window"

@pytest.mark.asyncio
async def test_create_window_commits_client_lookup_before_remote_create(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = ObservingRemoteConnection()
    ObservingRemoteConnection.observed_in_transaction = None
    app.state.client_connections = FakeConnectionRegistry(connection)

    async with db_client.session_factory() as session:
        windows_router._TEST_OBSERVED_SESSION = session
        try:
            response = await db_client.post(
                f"/api/clients/{remote_client_id}/windows",
                json={"cwd": "/tmp/remote", "shell_command": "/bin/bash"},
            )
        finally:
            delattr(windows_router, "_TEST_OBSERVED_SESSION")

    assert response.status_code == 200
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, response.json()["id"])
    assert ObservingRemoteConnection.observed_in_transaction is False

@pytest.mark.asyncio
async def test_create_window_returns_503_for_remote_client_until_runtime_exists(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    app.state.client_connections = FakeConnectionRegistry(None)

    response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/tmp", "shell_command": "/bin/bash"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "remote runtime unavailable"}
    assert FakeTmuxManager.killed_targets == []

    async with db_client.session_factory() as session:
        windows = (await session.execute(select(VirtualWindow))).scalars().all()
    assert windows == []
