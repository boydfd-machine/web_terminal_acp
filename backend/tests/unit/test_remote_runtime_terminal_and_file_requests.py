# ruff: noqa: F403, F405
from tests.unit.test_remote_runtime_support import *

@pytest.mark.asyncio
async def test_create_window_sends_request_and_returns_remote_runtime_window() -> None:
    client_id = uuid4()
    window_id = uuid4()
    response = AgentMessage(
        type="create_window_result",
        client_id=client_id,
        window_id=window_id,
        request_id="response-request",
        payload={
            "remote_session_id": "session-1",
            "remote_window_id": "window-2",
            "cwd": "/remote/project",
            "shell_command": "/bin/zsh",
        },
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    runtime_window = await runtime.create_window(cwd="/ignored", shell_command="/bin/bash", window_id=window_id)

    assert runtime_window == RuntimeWindow(
        session_id="session-1",
        window_id="window-2",
        cwd="/remote/project",
        shell_command="/bin/zsh",
    )
    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "create_window"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.request_id is not None
    assert message.payload == {"cwd": "/ignored", "shell_command": "/bin/bash"}


@pytest.mark.asyncio
async def test_create_window_can_request_isolated_clone_sessions() -> None:
    client_id = uuid4()
    window_id = uuid4()
    response = AgentMessage(
        type="create_window_result",
        client_id=client_id,
        window_id=window_id,
        request_id="response-request",
        payload={
            "remote_session_id": "session-1",
            "remote_window_id": "window-2",
        },
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    await runtime.create_window(
        cwd="/remote/project",
        shell_command="codex",
        window_id=window_id,
        clone_source_window_id="source-window",
        isolate_clone_sessions=True,
    )

    message, _timeout = connection.requests[0]
    assert message.payload == {
        "cwd": "/remote/project",
        "shell_command": "codex",
        "clone_source_window_id": "source-window",
        "isolate_clone_sessions": True,
    }


@pytest.mark.asyncio
async def test_create_window_sends_resolved_agent_model_settings() -> None:
    client_id = uuid4()
    window_id = uuid4()
    response = AgentMessage(
        type="create_window_result",
        client_id=client_id,
        window_id=window_id,
        request_id="response-request",
        payload={
            "remote_session_id": "session-1",
            "remote_window_id": "window-2",
        },
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    await runtime.create_window(
        cwd="/remote/project",
        shell_command="codex",
        window_id=window_id,
        agent_model_agent="codex",
        agent_model_settings={
            "preset_id": "openai-main",
            "provider": "openai_compatible",
            "base_url": "https://models.example.com/v1",
            "api_key": "secret-key",
            "model": "model-a",
        },
    )

    message, _timeout = connection.requests[0]
    assert message.payload == {
        "cwd": "/remote/project",
        "shell_command": "codex",
        "agent_model_agent": "codex",
        "agent_model_settings": {
            "preset_id": "openai-main",
            "provider": "openai_compatible",
            "base_url": "https://models.example.com/v1",
            "api_key": "secret-key",
            "model": "model-a",
        },
    }

@pytest.mark.asyncio
async def test_list_agent_clients_queries_remote_client() -> None:
    client_id = uuid4()
    response = AgentMessage(
        type="agent_client_result",
        client_id=client_id,
        request_id="response-request",
        payload={
            "agent_clients": [
                {
                    "id": "codex",
                    "provider_id": "codex",
                    "label": "Codex",
                    "aliases": [],
                    "default_command": "codex",
                    "command_names": ["codex"],
                }
            ]
        },
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    payload = await runtime.list_agent_clients()

    assert payload == response.payload
    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "agent_clients_list"
    assert message.client_id == client_id
    assert message.request_id is not None
    assert message.payload == {}

@pytest.mark.asyncio
async def test_create_window_raises_when_remote_client_is_unavailable() -> None:
    client_id = uuid4()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(None))

    with pytest.raises(RemoteClientUnavailable) as exc_info:
        await runtime.create_window(cwd=None, window_id=uuid4())
    assert exc_info.value.reason == "no_connection"

@pytest.mark.asyncio
async def test_create_window_raises_with_connection_closed_reason() -> None:
    client_id = uuid4()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(ClosedConnection()))

    with pytest.raises(RemoteClientUnavailable) as exc_info:
        await runtime.create_window(cwd=None, window_id=uuid4())
    assert exc_info.value.reason == "connection_closed"

@pytest.mark.asyncio
async def test_create_window_raises_with_request_timeout_reason() -> None:
    client_id = uuid4()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(TimeoutConnection()))

    with pytest.raises(RemoteClientUnavailable) as exc_info:
        await runtime.create_window(cwd=None, window_id=uuid4())
    assert exc_info.value.reason == "request_timeout"

@pytest.mark.asyncio
async def test_create_window_raises_with_request_closed_reason() -> None:
    client_id = uuid4()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(ClosingConnection()))

    with pytest.raises(RemoteClientUnavailable) as exc_info:
        await runtime.create_window(cwd=None, window_id=uuid4())
    assert exc_info.value.reason == "connection_closed"

@pytest.mark.asyncio
async def test_attach_sends_remote_terminal_attach_request() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=window_id,
            request_id="attach-response",
            payload={"ok": True},
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    async def ignored_sender(data: bytes) -> None:
        raise AssertionError("remote runtime does not call local sender directly")

    await runtime.attach(
        runtime_window,
        ignored_sender,
        local_window_id=window_id,
        allow_missing_window_recreate=True,
    )

    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 10.0
    assert message.type == "terminal_attach"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.request_id is not None
    assert message.payload == {
        "remote_session_id": "remote-session",
        "remote_window_id": "remote-window",
        "view_id": str(window_id),
        "allow_missing_window_recreate": True,
        "activity": "terminal_viewed",
    }


@pytest.mark.asyncio
async def test_attach_sends_remote_terminal_viewed_activity() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=window_id,
            request_id="attach-response",
            payload={"ok": True},
        )
    )

    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    async def ignored_sender(data: bytes) -> None:
        raise AssertionError("remote runtime does not call local sender directly")

    await runtime.attach(runtime_window, ignored_sender, local_window_id=window_id)

    message, _timeout = connection.requests[0]
    assert message.payload["activity"] == "terminal_viewed"


@pytest.mark.asyncio
async def test_active_processes_queries_remote_client() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="process_liveness_result",
            client_id=client_id,
            window_id=window_id,
            request_id="process-response",
            payload={"active_processes": ["sleep 120"]},
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    processes = await runtime.active_processes(runtime_window, local_window_id=window_id)

    assert processes == ["sleep 120"]
    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "process_liveness"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.request_id is not None
    assert message.payload == {
        "remote_session_id": "remote-session",
        "remote_window_id": "remote-window",
    }

@pytest.mark.asyncio
async def test_attach_returns_recreated_remote_runtime_window() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=window_id,
            request_id="attach-response",
            payload={
                "ok": True,
                "remote_session_id": "remote-session",
                "remote_window_id": "@9",
                "cwd": "/remote/project",
                "shell_command": "/bin/bash",
            },
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="@7")

    async def ignored_sender(data: bytes) -> None:
        raise AssertionError("remote runtime does not call local sender directly")

    attached_window = await runtime.attach(runtime_window, ignored_sender, local_window_id=window_id)

    assert attached_window == RuntimeWindow(
        session_id="remote-session",
        window_id="@9",
        cwd="/remote/project",
        shell_command="/bin/bash",
    )

@pytest.mark.asyncio
async def test_attach_raises_remote_terminal_error_when_client_reports_failure() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_error",
            client_id=client_id,
            window_id=window_id,
            request_id="attach-response",
            payload={"message": "tmux attach failed"},
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    async def ignored_sender(data: bytes) -> None:
        raise AssertionError("remote runtime does not call local sender directly")

    with pytest.raises(RemoteTerminalError, match="tmux attach failed"):
        await runtime.attach(runtime_window, ignored_sender, local_window_id=window_id)

@pytest.mark.asyncio
async def test_detach_sends_remote_terminal_detach_request() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    await runtime.detach(runtime_window, local_window_id=window_id)

    assert len(connection.sent) == 1
    message = connection.sent[0]
    assert message.type == "terminal_detach"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.payload == {
        "remote_session_id": "remote-session",
        "remote_window_id": "remote-window",
        "view_id": str(window_id),
    }

@pytest.mark.asyncio
async def test_send_input_sends_base64_terminal_payload() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    await runtime.send_input(runtime_window, b"whoami\n", local_window_id=window_id)

    assert len(connection.sent) == 1
    message = connection.sent[0]
    assert message.type == "terminal_input"
    assert message.client_id == client_id
    assert message.window_id == window_id
    payload = TerminalPayload.model_validate(message.payload)
    assert payload.window_id == window_id
    assert payload.to_bytes() == b"whoami\n"
    assert message.payload["view_id"] == str(window_id)

@pytest.mark.asyncio
async def test_send_input_direct_sends_base_window_terminal_payload() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    await runtime.send_input_direct(runtime_window, b"artifact prompt\n", local_window_id=window_id)

    assert len(connection.sent) == 1
    message = connection.sent[0]
    assert message.type == "terminal_input_direct"
    assert message.client_id == client_id
    assert message.window_id == window_id
    payload = TerminalPayload.model_validate(message.payload)
    assert payload.window_id == window_id
    assert payload.to_bytes() == b"artifact prompt\n"
    assert message.payload["remote_session_id"] == "remote-session"
    assert message.payload["remote_window_id"] == "remote-window"

@pytest.mark.asyncio
async def test_resize_sends_resize_message_with_browser_window_id() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    await runtime.resize(runtime_window, cols=120, rows=40, local_window_id=window_id)

    assert len(connection.sent) == 1
    message = connection.sent[0]
    assert message.type == "terminal_resize"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.payload == {"cols": 120, "rows": 40, "view_id": str(window_id)}

@pytest.mark.asyncio
async def test_capture_output_bytes_requests_remote_terminal_snapshot() -> None:
    client_id = uuid4()
    window_id = uuid4()
    response = AgentMessage(
        type="terminal_capture_result",
        client_id=client_id,
        window_id=window_id,
        request_id="capture-response",
        payload=TerminalPayload.from_bytes(window_id, b"current screen").model_dump(mode="json"),
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="@7")

    output = await runtime.capture_output_bytes(
        runtime_window,
        local_window_id=window_id,
        history_lines=5000,
    )

    assert output == b"current screen"
    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "terminal_capture"
    assert message.client_id == client_id
    assert message.window_id == window_id
    assert message.request_id is not None
    assert message.payload == {
        "remote_session_id": "remote-session",
        "remote_window_id": "@7",
        "history_lines": "5000",
    }

@pytest.mark.asyncio
async def test_read_file_bytes_requests_remote_client_file() -> None:
    client_id = uuid4()
    response = AgentMessage(
        type="file_read_result",
        client_id=client_id,
        request_id="file-read-response",
        payload=TerminalPayload.from_bytes(client_id, b'{"task":"demo"}').model_dump(mode="json"),
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    output = await runtime.read_file_bytes("/tmp/artifact.json", max_bytes=4096)

    assert output == b'{"task":"demo"}'
    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "file_read"
    assert message.client_id == client_id
    assert message.request_id is not None
    assert message.payload == {"path": "/tmp/artifact.json", "max_bytes": 4097}

@pytest.mark.asyncio
async def test_list_file_entries_requests_remote_client_files() -> None:
    client_id = uuid4()
    response = AgentMessage(
        type="file_list_result",
        client_id=client_id,
        request_id="file-list-response",
        payload={
            "entries": [
                {
                    "name": "README.md",
                    "path": "/tmp/project/README.md",
                    "kind": "file",
                    "size": 12,
                    "mtime": 123.5,
                }
            ]
        },
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    entries = await runtime.list_file_entries("/tmp/project")

    assert entries[0].name == "README.md"
    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "file_list"
    assert message.payload == {"path": "/tmp/project"}
