from tests.unit.test_client_agent_config_support import *

def test_load_populates_required_fields_defaults_and_https_websocket_url(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="https://control.example.com/")

    config = ClientAgentConfig.load(config_path)

    assert config.client_id == UUID("12345678-1234-5678-1234-567812345678")
    assert config.token == "secret-token"
    assert config.name == "edge-client"
    assert config.install_path == Path("/opt/web-terminal-acp-client")
    assert config.tmux_pool_session == "web_terminal_acp_pool"
    assert config.client_daemon_session == "web_terminal_acp_client"
    assert config.reconnect_initial_delay_seconds == 1
    assert config.reconnect_max_delay_seconds == 30
    assert config.websocket_ping_interval_seconds == 10
    assert config.websocket_ping_timeout_seconds == 60
    assert config.default_shell == default_user_shell()
    assert config.websocket_url == "wss://control.example.com/api/client-agent/ws"

def test_http_server_url_maps_to_ws_websocket_url(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="http://localhost:8000")

    config = ClientAgentConfig.load(config_path)

    assert config.websocket_url == "ws://localhost:8000/api/client-agent/ws"

def test_https_server_url_maps_to_bulk_websocket_url(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="https://control.example.com/")

    config = ClientAgentConfig.load(config_path)

    assert config.bulk_websocket_url == "wss://control.example.com/api/client-agent/bulk-ws"

def test_http_server_url_maps_to_bulk_websocket_url(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="http://localhost:8000")

    config = ClientAgentConfig.load(config_path)

    assert config.bulk_websocket_url == "ws://localhost:8000/api/client-agent/bulk-ws"

def test_explicit_bulk_websocket_url_is_preserved(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="ws://localhost:8000/api/client-agent/bulk-ws")

    config = ClientAgentConfig.load(config_path)

    assert config.bulk_websocket_url == "ws://localhost:8000/api/client-agent/bulk-ws"

def test_client_agent_lock_rejects_second_process(tmp_path: Path) -> None:
    config = ClientAgentConfig(
        client_id=UUID("12345678-1234-5678-1234-567812345678"),
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=tmp_path,
    )

    with client_agent_lock(config):
        try:
            with client_agent_lock(config):
                raise AssertionError("second lock unexpectedly acquired")
        except SystemExit as exc:
            assert exc.code == 2

async def test_run_client_agent_rejects_unexpected_bulk_ack(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")

    control_incoming_messages = [
        AgentMessage(type="hello_ack", client_id=client_id),
        AgentMessage(type="shutdown", client_id=client_id),
    ]
    bulk_incoming_messages = [AgentMessage(type="not_bulk_ack", client_id=client_id)]

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
            return []

        async def kill_stale_window(self, window_id: UUID) -> None:
            return None

    class FakeTerminalMultiplexer:
        async def close(self) -> None:
            return None

    class FakeWebSocket:
        def __init__(self, incoming_messages: list[AgentMessage]) -> None:
            self.incoming_messages = incoming_messages

        async def send(self, message: str) -> None:
            return None

        async def recv(self) -> str:
            return encode_agent_message(self.incoming_messages.pop(0))

    class FakeConnection:
        def __init__(self, websocket: FakeWebSocket) -> None:
            self.websocket = websocket

        async def __aenter__(self) -> FakeWebSocket:
            return self.websocket

        async def __aexit__(self, *args: object) -> None:
            return None

    def fake_connect(
        uri: str,
        *,
        extra_headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> FakeConnection:
        if uri.endswith("/api/client-agent/bulk-ws"):
            return FakeConnection(FakeWebSocket(bulk_incoming_messages))
        return FakeConnection(FakeWebSocket(control_incoming_messages))

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
    )

    with pytest.raises(RuntimeError, match="unexpected bulk websocket ack"):
        await client_agent_runner._run_client_agent_once(config)

async def test_run_client_agent_drains_bulk_websocket_after_hello(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    bulk_ack_received = asyncio.Event()

    control_incoming_messages = [
        AgentMessage(type="hello_ack", client_id=client_id),
        AgentMessage(type="shutdown", client_id=client_id),
    ]
    bulk_incoming_messages = [
        AgentMessage(type="bulk_hello_ack", client_id=client_id),
        AgentMessage(
            type="ai_event_ack",
            client_id=client_id,
            request_id="ai-event-1",
            payload={"ok": True},
        ),
    ]

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
            return []

        async def kill_stale_window(self, window_id: UUID) -> None:
            return None

    class FakeTerminalMultiplexer:
        async def close(self) -> None:
            return None

    class FakeWebSocket:
        def __init__(self, incoming_messages: list[AgentMessage], *, wait_for_bulk_ack: bool = False) -> None:
            self.incoming_messages = incoming_messages
            self.wait_for_bulk_ack = wait_for_bulk_ack

        async def send(self, message: str) -> None:
            return None

        async def recv(self) -> str:
            await asyncio.sleep(0)
            if self.wait_for_bulk_ack and self.incoming_messages[0].type == "shutdown":
                await bulk_ack_received.wait()
            if not self.incoming_messages:
                await asyncio.Event().wait()
            message = self.incoming_messages.pop(0)
            if message.type == "ai_event_ack":
                bulk_ack_received.set()
            return encode_agent_message(message)

    class FakeConnection:
        def __init__(self, websocket: FakeWebSocket) -> None:
            self.websocket = websocket

        async def __aenter__(self) -> FakeWebSocket:
            return self.websocket

        async def __aexit__(self, *args: object) -> None:
            return None

    def fake_connect(
        uri: str,
        *,
        extra_headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> FakeConnection:
        if uri.endswith("/api/client-agent/bulk-ws"):
            return FakeConnection(FakeWebSocket(bulk_incoming_messages))
        return FakeConnection(FakeWebSocket(control_incoming_messages, wait_for_bulk_ack=True))

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
    )

    task = asyncio.create_task(client_agent_runner._run_client_agent_once(config))
    try:
        await asyncio.wait_for(bulk_ack_received.wait(), timeout=0.2)
        assert await asyncio.wait_for(task, timeout=1) is True
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

def test_bulk_receive_rejects_unexpected_inbound_message() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")

    with pytest.raises(RuntimeError, match="unexpected bulk websocket message"):
        client_agent_runner._handle_bulk_message(
            AgentMessage(type="terminal_output", client_id=client_id),
            client_id,
        )

async def test_run_client_agent_handles_inventory_and_tmux_commands(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    control_sent_messages: list[dict[str, object]] = []
    bulk_sent_messages: list[dict[str, object]] = []
    connect_calls: list[tuple[str, dict[str, str] | None, dict[str, object]]] = []
    registered_windows: list[tuple[UUID, str, str]] = []
    inputs: list[tuple[UUID, bytes]] = []
    resizes: list[tuple[UUID, int, int]] = []

    incoming_messages = [
        AgentMessage(type="hello_ack", client_id=client_id),
        AgentMessage(
            type="create_window",
            client_id=client_id,
            window_id=window_id,
            request_id="request-1",
        ),
        AgentMessage(
            type="terminal_input",
            client_id=client_id,
            window_id=window_id,
            payload=TerminalPayload.from_bytes(window_id, b"echo hi\n").model_dump(mode="json"),
        ),
        AgentMessage(
            type="terminal_resize",
            client_id=client_id,
            window_id=window_id,
            payload={"cols": 120, "rows": 36},
        ),
        AgentMessage(type="shutdown", client_id=client_id),
    ]
    bulk_hello_ack = AgentMessage(type="bulk_hello_ack", client_id=client_id)

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
            return [ClientRuntimeWindow(remote_session_id="client_pool", remote_window_id="@1", local_window_id=window_id)]

        async def kill_stale_window(self, window_id: UUID) -> None:
            return None

        async def window_activity_timestamp(
            self,
            remote_window_id: str,
            *,
            remote_session_id: str | None = None,
        ) -> None:
            return None

        async def create_window(
            self,
            requested_window_id: UUID,
            cwd: str | None = None,
            shell_command: str | None = None,
            agent_ops_token: str | None = None,
        ) -> ClientRuntimeWindow:
            assert requested_window_id == window_id
            assert cwd is None
            assert shell_command is None
            assert agent_ops_token is None
            return ClientRuntimeWindow(
                remote_session_id="client_pool",
                remote_window_id="@9",
                local_window_id=window_id,
                managed_agent_tools=True,
            )

    class FakeTerminalMultiplexer:
        def register_window(
            self,
            registered_window_id: UUID,
            remote_session_id: str,
            remote_window_id: str,
        ) -> None:
            registered_windows.append((registered_window_id, remote_session_id, remote_window_id))

        async def send_input(self, input_window_id: UUID, data: bytes, *, view_id=None) -> None:
            inputs.append((input_window_id, data))

        async def resize(self, resize_window_id: UUID, *, cols: int, rows: int, view_id=None) -> None:
            resizes.append((resize_window_id, cols, rows))

        async def close(self) -> None:
            return None

    class FakeWebSocket:
        def __init__(
            self,
            incoming: list[AgentMessage],
            sent_messages: list[dict[str, object]],
        ) -> None:
            self._incoming = incoming
            self._sent_messages = sent_messages

        async def send(self, message: str) -> None:
            self._sent_messages.append(json.loads(message))

        async def recv(self) -> str:
            await asyncio.sleep(0)
            if not self._incoming:
                await asyncio.Event().wait()
            return encode_agent_message(self._incoming.pop(0))

    class FakeConnection:
        def __init__(self, websocket: FakeWebSocket) -> None:
            self.websocket = websocket

        async def __aenter__(self) -> FakeWebSocket:
            return self.websocket

        async def __aexit__(self, *args: object) -> None:
            return None

    def fake_connect(
        uri: str,
        *,
        extra_headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> FakeConnection:
        connect_calls.append((uri, extra_headers, kwargs))
        if uri.endswith("/api/client-agent/bulk-ws"):
            return FakeConnection(FakeWebSocket([bulk_hello_ack], bulk_sent_messages))
        return FakeConnection(FakeWebSocket(incoming_messages, control_sent_messages))

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
    )

    await asyncio.wait_for(client_agent_runner.run_client_agent(config), timeout=5)

    expected_headers = {
        "Authorization": "Bearer secret-token",
        "X-Client-Id": "12345678-1234-5678-1234-567812345678",
    }
    assert connect_calls == [
        (
            "ws://control.example.com/api/client-agent/ws",
            expected_headers,
            {"max_size": None, "ping_interval": 10, "ping_timeout": 60},
        ),
        (
            "ws://control.example.com/api/client-agent/bulk-ws",
            expected_headers,
            {"max_size": None, "ping_interval": 10, "ping_timeout": 60},
        ),
    ]
    assert control_sent_messages[0] == {
        "type": "hello",
        "client_id": str(client_id),
        "window_id": None,
        "request_id": None,
        "payload": {
            "hostname": control_sent_messages[0]["payload"]["hostname"],
            "name": "edge-client",
            "version": __version__,
        },
    }
    assert bulk_sent_messages[0] == {
        "type": "bulk_hello",
        "client_id": str(client_id),
        "window_id": None,
        "request_id": None,
        "payload": {"version": __version__},
    }
    assert control_sent_messages[1] == {
        "type": "inventory",
        "client_id": str(client_id),
        "window_id": None,
        "request_id": None,
        "payload": {
            "windows": [
                {
                    "remote_session_id": "client_pool",
                    "remote_window_id": "@1",
                    "local_window_id": str(window_id),
                    "cwd": None,
                    "shell_command": None,
                    "managed_agent_tools": False,
                }
            ]
        },
    }
    assert {
        "type": "create_window_result",
        "client_id": str(client_id),
        "window_id": str(window_id),
        "request_id": "request-1",
        "payload": {
            "remote_session_id": "client_pool",
            "remote_window_id": "@9",
            "local_window_id": str(window_id),
            "cwd": None,
            "shell_command": None,
            "managed_agent_tools": True,
        },
    } in control_sent_messages
    assert registered_windows == [(window_id, "client_pool", "@1"), (window_id, "client_pool", "@9")]
    assert inputs == [(window_id, b"echo hi\n")]
    assert resizes == [(window_id, 120, 36)]
