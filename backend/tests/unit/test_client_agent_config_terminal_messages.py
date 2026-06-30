from tests.unit.test_client_agent_config_support import *

async def test_run_client_agent_reconnects_after_connection_loss(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    connect_calls: list[str] = []
    control_sent_messages_by_connection: list[list[dict[str, object]]] = []

    class FakeRuntime:
        def __init__(
            self,
            *,
            client_id: UUID,
            server_url: str,
            pool_session: str,
            default_shell: str,
            **kwargs: object,
        ) -> None:
            self.client_id = client_id
            self.server_url = server_url
            self.pool_session = pool_session
            self.default_shell = default_shell

        async def list_windows(self) -> list[ClientRuntimeWindow]:
            return [
                ClientRuntimeWindow(
                    remote_session_id="client_pool",
                    remote_window_id="@1",
                    local_window_id=window_id,
                )
            ]

        async def kill_stale_window(self, window_id: UUID) -> None:
            return None

        async def window_activity_timestamp(
            self,
            remote_window_id: str,
            *,
            remote_session_id: str | None = None,
        ) -> None:
            return None

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            return None

        async def close(self) -> None:
            return None

    class FakeWebSocket:
        def __init__(
            self,
            incoming_messages: list[AgentMessage],
            *,
            record_sent: bool,
            fail_when_empty: bool = False,
        ) -> None:
            self.incoming_messages = incoming_messages
            self.fail_when_empty = fail_when_empty
            self.sent_messages: list[dict[str, object]] = []
            if record_sent:
                control_sent_messages_by_connection.append(self.sent_messages)

        async def send(self, message: str) -> None:
            self.sent_messages.append(json.loads(message))

        async def recv(self) -> str:
            if not self.incoming_messages:
                if self.fail_when_empty:
                    raise OSError("server restarted")
                await asyncio.Event().wait()
            return encode_agent_message(self.incoming_messages.pop(0))

    class FakeConnection:
        def __init__(self, websocket: FakeWebSocket) -> None:
            self.websocket = websocket

        async def __aenter__(self) -> FakeWebSocket:
            return self.websocket

        async def __aexit__(self, *args: object) -> None:
            return None

    control_connection_messages = [
        [AgentMessage(type="hello_ack", client_id=client_id)],
        [
            AgentMessage(type="hello_ack", client_id=client_id),
            AgentMessage(type="shutdown", client_id=client_id),
        ],
    ]
    bulk_connection_messages = [
        [AgentMessage(type="bulk_hello_ack", client_id=client_id)],
        [AgentMessage(type="bulk_hello_ack", client_id=client_id)],
    ]

    def fake_connect(
        uri: str,
        *,
        extra_headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> FakeConnection:
        connect_calls.append(uri)
        assert extra_headers is not None
        if uri.endswith("/api/client-agent/bulk-ws"):
            return FakeConnection(FakeWebSocket(bulk_connection_messages.pop(0), record_sent=False))
        return FakeConnection(
            FakeWebSocket(
                control_connection_messages.pop(0),
                record_sent=True,
                fail_when_empty=True,
            )
        )

    monkeypatch.setattr(client_agent_runner.websockets, "connect", fake_connect)
    monkeypatch.setattr(client_agent_runner, "ClientTmuxRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        client_agent_runner,
        "ClientTerminalMultiplexer",
        FakeTerminalMultiplexer,
        raising=False,
    )

    config = ClientAgentConfig(
        client_id=client_id,
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=Path("/opt/web-terminal-acp-client"),
        tmux_pool_session="client_pool",
        reconnect_initial_delay_seconds=0,
        reconnect_max_delay_seconds=1,
    )

    await asyncio.wait_for(client_agent_runner.run_client_agent(config), timeout=1)

    assert connect_calls == [
        "ws://control.example.com/api/client-agent/ws",
        "ws://control.example.com/api/client-agent/bulk-ws",
        "ws://control.example.com/api/client-agent/ws",
        "ws://control.example.com/api/client-agent/bulk-ws",
    ]
    assert [messages[1]["type"] for messages in control_sent_messages_by_connection] == [
        "inventory",
        "inventory",
    ]

async def test_send_terminal_output_preserves_raw_bytes() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingBulkWriter(sent_messages)

    await client_agent_runner._send_terminal_output(
        writer,
        client_id,
        window_id,
        b"\x1b[31mtmux\x1b[0m",
    )

    payloads = [TerminalPayload.model_validate(message["payload"]) for message in sent_messages]
    assert [payload.to_bytes() for payload in payloads] == [b"\x1b[31mtmux\x1b[0m"]

async def test_send_terminal_output_can_mark_attach_snapshot() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingBulkWriter(sent_messages)

    await client_agent_runner._send_terminal_output(
        writer,
        client_id,
        window_id,
        b"prompt$ ",
        is_snapshot=True,
    )

    assert sent_messages[0]["payload"]["is_snapshot"] is True
    payload = TerminalPayload.model_validate(sent_messages[0]["payload"])
    assert payload.to_bytes() == b"prompt$ "

async def test_terminal_attach_marks_initial_pty_output_as_snapshot() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            return None

        async def attach_with_selection(self, attached_window_id: UUID, sender, selection_sender=None, view_id=None) -> None:
            await sender(b"prompt$ ")

    control_writer = _CollectingControlWriter([])
    bulk_writer = _CollectingBulkWriter(sent_messages)

    await client_agent_runner._handle_agent_message(
        control_writer,
        bulk_writer,
        ClientAgentConfig(
            client_id=client_id,
            token="secret-token",
            server_url="http://control.example.com",
            name="edge-client",
            install_path=Path("/opt/web-terminal-acp-client"),
        ),
        _ExistingRuntime(),
        FakeTerminalMultiplexer(),
        _NoopIdleSupervisor(),
        _NoopAgentToolWatcher(),
        _NoopAuxTerminal(),
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=client_id,
            window_id=window_id,
            payload={"remote_session_id": "client_pool", "remote_window_id": "@1"},
        ),
    )

    output_messages = [message for message in sent_messages if message["type"] == "terminal_output"]
    assert output_messages[0]["payload"]["is_snapshot"] is True
    payload = TerminalPayload.model_validate(output_messages[0]["payload"])
    assert payload.to_bytes() == b"prompt$ "

async def test_terminal_attach_keeps_later_pty_output_recordable() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            return None

        async def attach_with_selection(self, attached_window_id: UUID, sender, selection_sender=None, view_id=None) -> None:
            await sender(b"prompt$ ")
            await sender(b"real output\n")

    control_writer = _CollectingControlWriter([])
    bulk_writer = _CollectingBulkWriter(sent_messages)

    await client_agent_runner._handle_agent_message(
        control_writer,
        bulk_writer,
        ClientAgentConfig(
            client_id=client_id,
            token="secret-token",
            server_url="http://control.example.com",
            name="edge-client",
            install_path=Path("/opt/web-terminal-acp-client"),
        ),
        _ExistingRuntime(),
        FakeTerminalMultiplexer(),
        _NoopIdleSupervisor(),
        _NoopAgentToolWatcher(),
        _NoopAuxTerminal(),
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=client_id,
            window_id=window_id,
            payload={"remote_session_id": "client_pool", "remote_window_id": "@1"},
        ),
    )

    output_messages = [message for message in sent_messages if message["type"] == "terminal_output"]
    assert output_messages[0]["payload"]["is_snapshot"] is True
    assert "is_snapshot" not in output_messages[1]["payload"]
    payload = TerminalPayload.model_validate(output_messages[1]["payload"])
    assert payload.to_bytes() == b"real output\n"

async def test_silent_attach_does_not_send_capture_pane_text_as_terminal_output() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []
    captured_sender = None

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            return None

        async def attach_with_selection(self, attached_window_id: UUID, sender, selection_sender=None, view_id=None) -> None:
            nonlocal captured_sender
            captured_sender = sender

        async def capture_output_bytes(self, captured_window_id: UUID, *, view_id=None, history_lines=None) -> bytes:
            raise AssertionError("silent attach must not publish capture-pane text")

    control_writer = _CollectingControlWriter([])
    bulk_writer = _CollectingBulkWriter(sent_messages)

    attach_snapshot_tasks: dict[UUID, asyncio.Task[None]] = {}
    await client_agent_runner._handle_agent_message(
        control_writer,
        bulk_writer,
        ClientAgentConfig(
            client_id=client_id,
            token="secret-token",
            server_url="http://control.example.com",
            name="edge-client",
            install_path=Path("/opt/web-terminal-acp-client"),
        ),
        _ExistingRuntime(),
        FakeTerminalMultiplexer(),
        _NoopIdleSupervisor(),
        _NoopAgentToolWatcher(),
        _NoopAuxTerminal(),
        attach_snapshot_tasks,
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=client_id,
            window_id=window_id,
            payload={"remote_session_id": "client_pool", "remote_window_id": "@1"},
        ),
    )

    await attach_snapshot_tasks[window_id]
    assert captured_sender is not None
    assert [message for message in sent_messages if message["type"] == "terminal_output"] == []
    await captured_sender(b"real output\n")

    output_messages = [message for message in sent_messages if message["type"] == "terminal_output"]
    assert len(output_messages) == 1
    assert "is_snapshot" not in output_messages[0]["payload"]
    payload = TerminalPayload.model_validate(output_messages[0]["payload"])
    assert payload.to_bytes() == b"real output\n"

async def test_terminal_detach_cancels_pending_attach_snapshot() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            return None

        async def attach_with_selection(self, attached_window_id: UUID, sender, selection_sender=None, view_id=None) -> None:
            return None

        async def detach(self, detached_window_id: UUID, *, view_id=None) -> None:
            return None

        async def capture_output_bytes(self, captured_window_id: UUID, *, view_id=None, history_lines=None) -> bytes:
            return b"prompt$ "

    control_writer = _CollectingControlWriter([])
    bulk_writer = _CollectingBulkWriter([])

    attach_snapshot_tasks: dict[UUID, asyncio.Task[None]] = {}
    config = ClientAgentConfig(
        client_id=client_id,
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=Path("/opt/web-terminal-acp-client"),
    )
    terminal = FakeTerminalMultiplexer()
    await client_agent_runner._handle_agent_message(
        control_writer,
        bulk_writer,
        config,
        _ExistingRuntime(),
        terminal,
        _NoopIdleSupervisor(),
        _NoopAgentToolWatcher(),
        _NoopAuxTerminal(),
        attach_snapshot_tasks,
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=client_id,
            window_id=window_id,
            payload={"remote_session_id": "client_pool", "remote_window_id": "@1"},
        ),
    )

    await client_agent_runner._handle_agent_message(
        control_writer,
        bulk_writer,
        config,
        _ExistingRuntime(),
        terminal,
        _NoopIdleSupervisor(),
        _NoopAgentToolWatcher(),
        _NoopAuxTerminal(),
        attach_snapshot_tasks,
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(type="terminal_detach", client_id=client_id, window_id=window_id),
    )

    assert window_id not in attach_snapshot_tasks

async def test_send_terminal_selection_uses_terminal_selection_message() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingControlWriter(sent_messages)

    await client_agent_runner._send_terminal_selection(writer, client_id, window_id)

    assert sent_messages == [
        {
            "type": "terminal_selection",
            "client_id": str(client_id),
            "window_id": str(window_id),
            "request_id": None,
            "payload": {},
        }
    ]
