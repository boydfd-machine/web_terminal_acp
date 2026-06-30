# ruff: noqa: F403, F405
from tests.unit.test_remote_runtime_support import *

@pytest.mark.asyncio
async def test_write_file_bytes_requests_remote_client_file_write() -> None:
    client_id = uuid4()
    response = AgentMessage(
        type="file_write_result",
        client_id=client_id,
        request_id="file-write-response",
        payload={"path": "/tmp/project/upload.txt"},
    )
    connection = FakeConnection(response)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)

    await runtime.write_file_bytes("/tmp/project/upload.txt", b"uploaded", overwrite=False)

    message, timeout = connection.requests[0]
    assert timeout == 7.5
    assert message.type == "file_write"
    assert message.payload["path"] == "/tmp/project/upload.txt"
    assert message.payload["overwrite"] is False
    assert TerminalPayload.model_validate(message.payload).to_bytes() == b"uploaded"

@pytest.mark.asyncio
async def test_resize_ignores_repeated_dimensions_for_same_window() -> None:
    client_id = uuid4()
    window_id = uuid4()
    connection = FakeConnection()
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")

    await runtime.resize(runtime_window, cols=120, rows=40, local_window_id=window_id)
    await runtime.resize(runtime_window, cols=120, rows=40, local_window_id=window_id)
    await runtime.resize(runtime_window, cols=121, rows=40, local_window_id=window_id)

    assert [message.payload for message in connection.sent] == [
        {"cols": 120, "rows": 40, "view_id": str(window_id)},
        {"cols": 121, "rows": 40, "view_id": str(window_id)},
    ]

@pytest.mark.asyncio
async def test_select_window_sends_view_scoped_remote_request() -> None:
    client_id = uuid4()
    view_id = uuid4()
    next_window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=next_window_id,
            request_id="select-response",
            payload={"ok": True},
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))

    await runtime.select_window(
        RuntimeWindow(session_id="remote-session", window_id="@1"),
        RuntimeWindow(session_id="remote-session", window_id="@2"),
        local_window_id=next_window_id,
        view_id=view_id,
        allow_missing_window_recreate=True,
    )

    assert len(connection.requests) == 1
    message, timeout = connection.requests[0]
    assert timeout == 10.0
    assert message.type == "terminal_select_window"
    assert message.client_id == client_id
    assert message.window_id == next_window_id
    assert message.payload == {
        "remote_session_id": "remote-session",
        "remote_window_id": "@2",
        "view_id": str(view_id),
        "allow_missing_window_recreate": True,
        "activity": "terminal_viewed",
    }


@pytest.mark.asyncio
async def test_select_window_sends_remote_terminal_viewed_activity() -> None:
    client_id = uuid4()
    view_id = uuid4()
    next_window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=next_window_id,
            request_id="select-response",
            payload={"ok": True},
        )
    )

    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))

    await runtime.select_window(
        RuntimeWindow(session_id="remote-session", window_id="@1"),
        RuntimeWindow(session_id="remote-session", window_id="@2"),
        local_window_id=next_window_id,
        view_id=view_id,
    )

    message, _timeout = connection.requests[0]
    assert message.payload["activity"] == "terminal_viewed"

@pytest.mark.asyncio
async def test_select_window_returns_recreated_remote_runtime_window() -> None:
    client_id = uuid4()
    view_id = uuid4()
    next_window_id = uuid4()
    connection = FakeConnection(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=next_window_id,
            request_id="select-response",
            payload={
                "ok": True,
                "remote_session_id": "remote-session",
                "remote_window_id": "@9",
            },
        )
    )
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection))

    selected_window = await runtime.select_window(
        RuntimeWindow(session_id="remote-session", window_id="@1"),
        RuntimeWindow(session_id="remote-session", window_id="@2", cwd="/workspace/project"),
        local_window_id=next_window_id,
        view_id=view_id,
    )

    assert selected_window == RuntimeWindow(
        session_id="remote-session",
        window_id="@9",
        cwd="/workspace/project",
    )
