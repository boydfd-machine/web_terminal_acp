from tests.unit.test_terminal_router_support import *

def test_mark_window_error_updates_window_status():
    window = VirtualWindow(title="Terminal", status=WindowStatus.active)

    mark_window_error(window)

    assert window.status is WindowStatus.error

def test_mark_window_active_updates_window_status():
    window = VirtualWindow(title="Terminal", status=WindowStatus.error)

    mark_window_active(window)

    assert window.status is WindowStatus.active

def test_mark_window_disconnected_updates_window_status():
    window = VirtualWindow(title="Terminal", status=WindowStatus.active)

    mark_window_disconnected(window)

    assert window.status is WindowStatus.disconnected

def test_scoped_terminal_websocket_route_is_registered():
    paths = {getattr(route, "path", None) for route in terminal.router.routes}

    assert "/api/clients/{client_id}/terminal/{window_id}" in paths

@pytest.mark.asyncio
async def test_scoped_terminal_route_rejects_window_for_different_client(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    calls = []

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        calls.append((requested_client_id, requested_window_id))
        return None

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert calls == [(client_id, window_id)]
    assert websocket.accepted is False
    assert websocket.closed == [status.WS_1008_POLICY_VIOLATION]

@pytest.mark.asyncio
async def test_scoped_terminal_route_reports_disconnected_local_window(monkeypatch) -> None:
    client_id = LOCAL_CLIENT_ID
    window_id = uuid4()
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.disconnected,
        tmux_session="web-terminal",
        tmux_window_id="@7",
    )

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == client_id
        assert requested_window_id == window_id
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert websocket.sent_text == [
        '{"type":"terminal_status","status":"unavailable","reason":"client_offline",'
        '"retry_after_ms":5000}'
    ]
    assert websocket.closed == [1000]

@pytest.mark.asyncio
async def test_scoped_terminal_route_reports_runtime_starting_window(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
    )

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == client_id
        assert requested_window_id == window_id
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert websocket.sent_text == [
        '{"type":"terminal_status","status":"reconnecting","reason":"runtime_starting",'
        '"retry_after_ms":500}'
    ]
    assert websocket.closed == [1013]

@pytest.mark.asyncio
async def test_scoped_terminal_route_attaches_even_when_local_tmux_window_was_missing(monkeypatch) -> None:
    window_id = uuid4()
    window = VirtualWindow(
        id=window_id,
        client_id=LOCAL_CLIENT_ID,
        title="Terminal",
        status=WindowStatus.active,
        tmux_session="web-terminal",
        tmux_window_id="@7",
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

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert websocket.sent_text == ['{"type":"terminal_status","status":"connected"}']
    assert websocket.closed == []
    assert window.status is WindowStatus.active
    assert broker.attachments == [
        (
            LOCAL_CLIENT_ID,
            window_id,
            RuntimeWindow(session_id="web-terminal", window_id="@7"),
            broker.attachments[0][3],
            broker.attachments[0][4],
            window_id,
        )
    ]

@pytest.mark.asyncio
async def test_scoped_terminal_route_recovers_disconnected_remote_window(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="@131")
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.disconnected,
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
    websocket = FakeWebSocket()
    websocket.app.state.client_connections = SimpleNamespace(get=lambda requested_client_id: object())

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert websocket.sent_text == ['{"type":"terminal_status","status":"connected"}']
    assert window.status is WindowStatus.active
    assert broker.attachments == [(client_id, window_id, runtime_window, None, None, window_id)]
    assert websocket.closed == []

@pytest.mark.asyncio
async def test_remote_attach_timeout_does_not_raise_when_browser_already_closed(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="@131")
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        remote_session_id=runtime_window.session_id,
        remote_window_id=runtime_window.window_id,
    )

    class TimeoutBroker(FakeBroker):
        async def attach(self, *args, **kwargs):
            await super().attach(*args, **kwargs)
            raise terminal.RemoteClientUnavailable("remote client unavailable", reason="request_timeout")

    class AlreadyClosedWebSocket(FakeWebSocket):
        async def send_text(self, data: str) -> None:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    broker = TimeoutBroker()

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    websocket = AlreadyClosedWebSocket()
    websocket.app.state.client_connections = SimpleNamespace(get=lambda requested_client_id: object())

    await terminal.terminal_websocket(websocket, client_id, window_id, tmux_manager=object())

    assert websocket.accepted is True
    assert window.status is WindowStatus.disconnected
    assert broker.unsubscriptions == [(client_id, window_id, websocket.send_bytes, websocket.send_text)]


@pytest.mark.asyncio
async def test_scoped_terminal_route_attaches_local_runtime_and_routes_input(monkeypatch) -> None:
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

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == LOCAL_CLIENT_ID
        assert requested_window_id == window_id
        return window

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    websocket = FakeWebSocket(
        [
            {"bytes": b"whoami\n"},
            {"text": '{"type":"resize","cols":120,"rows":40}'},
            {"text": "pwd\n"},
        ]
    )

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())

    assert websocket.accepted is True
    assert broker.subscriptions == [(LOCAL_CLIENT_ID, window_id, websocket.send_bytes, websocket.send_text)]
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
    assert broker.attachments[0][4] is not None
    assert broker.inputs == [
        (LOCAL_CLIENT_ID, window_id, runtime_window, b"whoami\n", window_id),
        (LOCAL_CLIENT_ID, window_id, runtime_window, b"pwd\n", window_id),
    ]
    assert broker.resizes == [(LOCAL_CLIENT_ID, window_id, runtime_window, 120, 40, window_id)]
    assert websocket.sent_text == ['{"type":"terminal_status","status":"connected"}']
    assert broker.unsubscriptions == [(LOCAL_CLIENT_ID, window_id, websocket.send_bytes, websocket.send_text)]

@pytest.mark.asyncio
async def test_scoped_terminal_route_does_not_record_initial_attach_snapshot(monkeypatch) -> None:
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
    recorded_output: list[bytes] = []

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        return window

    async def fake_record_terminal_command_markers(session, client_id, target_window_id, commands):
        return []

    async def fake_record_terminal_output_chunk(session, client_id, target_window_id, data, es_client):
        recorded_output.append(data)

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    monkeypatch.setattr(terminal, "record_terminal_command_markers", fake_record_terminal_command_markers)
    monkeypatch.setattr(terminal, "record_terminal_output_chunk", fake_record_terminal_output_chunk)
    monkeypatch.setattr(terminal, "ATTACH_SNAPSHOT_GRACE_SECONDS", 0.01)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())

    output_callback = broker.attachments[0][3]
    await output_callback(b"old screen\n")
    await asyncio.sleep(0.02)
    await output_callback(b"live output\n")
    for _ in range(20):
        if recorded_output == [b"live output\n"]:
            break
        await asyncio.sleep(0.01)

    assert recorded_output == [b"live output\n"]
    assert broker.published_output == [
        (LOCAL_CLIENT_ID, window_id, b"old screen\n"),
        (LOCAL_CLIENT_ID, window_id, b"live output\n"),
    ]

@pytest.mark.asyncio
async def test_scoped_terminal_route_does_not_record_multi_chunk_initial_attach_snapshot(monkeypatch) -> None:
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
    recorded_output: list[bytes] = []

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        return window

    async def fake_record_terminal_command_markers(session, client_id, target_window_id, commands):
        return []

    async def fake_record_terminal_output_chunk(session, client_id, target_window_id, data, es_client):
        recorded_output.append(data)

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    monkeypatch.setattr(terminal, "record_terminal_command_markers", fake_record_terminal_command_markers)
    monkeypatch.setattr(terminal, "record_terminal_output_chunk", fake_record_terminal_output_chunk)
    monkeypatch.setattr(terminal, "ATTACH_SNAPSHOT_GRACE_SECONDS", 0.01, raising=False)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())

    output_callback = broker.attachments[0][3]
    await output_callback(b"\x1b[?25l\x1b[37C")
    await output_callback(b"\xe2\x94\x82\xc2\xb7\xc2\xb7\xc2\xb7")
    await asyncio.sleep(0.02)
    await output_callback(b"live output\n")
    for _ in range(20):
        if recorded_output == [b"live output\n"]:
            break
        await asyncio.sleep(0.01)

    assert recorded_output == [b"live output\n"]
    assert broker.published_output == [
        (LOCAL_CLIENT_ID, window_id, b"\x1b[?25l\x1b[37C"),
        (LOCAL_CLIENT_ID, window_id, b"\xe2\x94\x82\xc2\xb7\xc2\xb7\xc2\xb7"),
        (LOCAL_CLIENT_ID, window_id, b"live output\n"),
    ]

@pytest.mark.asyncio
async def test_local_terminal_batches_rapid_output_recording_without_delaying_display(monkeypatch) -> None:
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
    recorded_output: list[bytes] = []

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        return window

    async def fake_record_terminal_command_markers(session, client_id, target_window_id, commands):
        return []

    async def fake_record_terminal_output_chunk(session, client_id, target_window_id, data, es_client):
        recorded_output.append(data)
        return object()

    monkeypatch.setattr(terminal, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(terminal, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(terminal, "_terminal_broker", lambda websocket, tmux_manager: broker)
    monkeypatch.setattr(terminal, "record_terminal_command_markers", fake_record_terminal_command_markers)
    monkeypatch.setattr(terminal, "record_terminal_output_chunk", fake_record_terminal_output_chunk)
    monkeypatch.setattr(terminal, "ATTACH_SNAPSHOT_GRACE_SECONDS", -1.0, raising=False)
    websocket = FakeWebSocket()

    await terminal.terminal_websocket(websocket, LOCAL_CLIENT_ID, window_id, tmux_manager=ExistingTmuxManager())
    output_callback = broker.attachments[0][3]

    await output_callback(b"one")
    await output_callback(b"two")

    assert broker.published_output == [
        (LOCAL_CLIENT_ID, window_id, b"one"),
        (LOCAL_CLIENT_ID, window_id, b"two"),
    ]

    for _ in range(20):
        if recorded_output == [b"onetwo"]:
            break
        await asyncio.sleep(0.01)

    assert recorded_output == [b"onetwo"]
