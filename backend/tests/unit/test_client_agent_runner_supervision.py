from tests.unit.test_client_agent_config_support import *


async def test_run_client_agent_reconnects_when_control_writer_send_fails(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    send_attempted = asyncio.Event()
    control_incoming_messages = [AgentMessage(type="hello_ack", client_id=client_id)]
    bulk_incoming_messages = [AgentMessage(type="bulk_hello_ack", client_id=client_id)]

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
            return None

        async def list_windows(self) -> list[ClientRuntimeWindow]:
            return []

        async def kill_stale_window(self, window_id: UUID) -> None:
            return None

    class FakeTerminalMultiplexer:
        async def close(self) -> None:
            return None

    class FakeWebSocket:
        def __init__(self, incoming_messages: list[AgentMessage], *, fail_send: bool = False) -> None:
            self.incoming_messages = incoming_messages
            self.fail_send = fail_send

        async def send(self, message: str) -> None:
            if self.fail_send and "heartbeat" in message:
                send_attempted.set()
                raise OSError("socket send failed")

        async def recv(self) -> str:
            await asyncio.sleep(0)
            if not self.incoming_messages:
                await asyncio.Event().wait()
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
        return FakeConnection(FakeWebSocket(control_incoming_messages, fail_send=True))

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
        await asyncio.wait_for(send_attempted.wait(), timeout=0.5)
        with pytest.raises(OSError, match="socket send failed"):
            await asyncio.wait_for(task, timeout=0.5)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
