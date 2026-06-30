from tests.unit.test_terminal_router_support import *

@pytest.mark.asyncio
async def test_local_terminal_records_output_before_slow_git_worktree_tracking(monkeypatch) -> None:
    window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="web-terminal", window_id="@7")
    window = VirtualWindow(
        id=window_id,
        client_id=LOCAL_CLIENT_ID,
        title="Terminal",
        status=WindowStatus.active,
        tmux_session=runtime_window.session_id,
        tmux_window_id=runtime_window.window_id,
    )
    broker = FakeBroker()
    ui_calls: list[tuple[str, list[str], str | None]] = []
    recorded_output: list[bytes] = []
    git_started = asyncio.Event()
    git_continue = asyncio.Event()
    git_done = asyncio.Event()

    class FakeMarkerExtractor:
        def feed(self, data: bytes):
            return (
                b"visible output\n",
                [
                    {
                        "window_id": str(window_id),
                        "phase": "started",
                        "command": "echo hi",
                        "sequence": "1",
                    }
                ],
                [
                    {
                        "window_id": str(window_id),
                        "worktree_root": "/tmp/agent-worktree",
                        "main_repo_root": "/tmp/main",
                    }
                ],
            )

    class FakeUiHub:
        async def publish_invalidation(self, resources, *, reason=None, **kwargs):
            ui_calls.append(("invalidate", list(resources), reason))

        async def publish_debounced_invalidation(self, key, resources, *, reason=None, **kwargs):
            ui_calls.append(("debounced", list(resources), reason))

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        return window

    async def fake_record_terminal_command_markers(session, client_id, target_window_id, commands):
        return [object()]

    async def fake_record_terminal_output_chunk(session, client_id, target_window_id, data, es_client):
        recorded_output.append(data)
        return object()

    async def fake_process_worktree_registration(*args, **kwargs):
        git_started.set()
        await git_continue.wait()

    async def fake_process_git_worktree_snapshot_refresh(*args, **kwargs):
        git_done.set()
        return True

    async def fake_refresh_project_todo_worktree_summaries_for_window(*args, **kwargs):
        return False

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    monkeypatch.setattr(terminal, "_ui_event_hub", lambda websocket: FakeUiHub())
    monkeypatch.setattr(terminal, "TerminalStreamMarkerExtractor", FakeMarkerExtractor)
    monkeypatch.setattr(terminal, "record_terminal_command_markers", fake_record_terminal_command_markers)
    monkeypatch.setattr(terminal, "record_terminal_output_chunk", fake_record_terminal_output_chunk)
    monkeypatch.setattr(terminal, "process_worktree_registration", fake_process_worktree_registration)
    monkeypatch.setattr(
        terminal,
        "process_git_worktree_snapshot_refresh",
        fake_process_git_worktree_snapshot_refresh,
    )
    monkeypatch.setattr(
        terminal,
        "refresh_project_todo_worktree_summaries_for_window",
        fake_refresh_project_todo_worktree_summaries_for_window,
    )
    monkeypatch.setattr(terminal, "ATTACH_SNAPSHOT_GRACE_SECONDS", -1.0, raising=False)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())
    output_callback = broker.attachments[0][3]

    try:
        await output_callback(b"raw output")
        await asyncio.wait_for(git_started.wait(), timeout=1)

        assert recorded_output == [b"visible output\n"]
        assert (
            "invalidate",
            ["agent_record", "command_history", "window", "search"],
            "terminal_command",
        ) in ui_calls
        assert ("debounced", ["window", "search"], "terminal_output") in ui_calls
        assert git_done.is_set() is False
    finally:
        git_continue.set()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(git_done.wait(), timeout=1)

@pytest.mark.asyncio
async def test_scoped_terminal_route_marks_error_window_active_after_successful_attach(monkeypatch) -> None:
    window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="web-terminal", window_id="@7")
    window = VirtualWindow(
        id=window_id,
        client_id=LOCAL_CLIENT_ID,
        title="Terminal",
        status=WindowStatus.error,
        tmux_session=runtime_window.session_id,
        tmux_window_id=runtime_window.window_id,
    )
    broker = FakeBroker()

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == LOCAL_CLIENT_ID
        assert requested_window_id == window_id
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())

    assert websocket.accepted is True
    assert websocket.sent_text == ['{"type":"terminal_status","status":"connected"}']
    assert window.status is WindowStatus.active
    assert broker.attachments == [
        (
            LOCAL_CLIENT_ID,
            window_id,
            runtime_window,
            broker.attachments[0][3],
            broker.attachments[0][4],
            window_id,
        )
    ]

@pytest.mark.asyncio
async def test_scoped_terminal_route_routes_remote_window_input_and_resize(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="remote-window")
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        remote_session_id=runtime_window.session_id,
        remote_window_id=runtime_window.window_id,
    )
    broker = FakeBroker()

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == client_id
        assert requested_window_id == window_id
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    websocket = FakeWebSocket(
        [
            {"text": "ls\n"},
            {"text": '{"type":"resize","cols":100,"rows":28}'},
        ]
    )
    websocket.app.state.client_connections = SimpleNamespace(get=lambda requested_client_id: object())

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert websocket.sent_text == ['{"type":"terminal_status","status":"connected"}']
    assert broker.attachments == [(client_id, window_id, runtime_window, None, None, window_id)]
    assert broker.inputs == [(client_id, window_id, runtime_window, b"ls\n", window_id)]
    assert broker.resizes == [(client_id, window_id, runtime_window, 100, 28, window_id)]
    assert broker.unsubscriptions == [(client_id, window_id, websocket.send_bytes, websocket.send_text)]
