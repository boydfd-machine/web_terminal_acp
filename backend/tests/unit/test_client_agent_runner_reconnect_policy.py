from tests.unit.test_client_agent_runner_support import *


@pytest.mark.asyncio
async def test_run_client_agent_adds_jitter_to_reconnect_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    attempts = 0
    sleeps: list[float] = []

    async def fake_run_once(config: ClientAgentConfig) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise OSError("network unavailable")
        return True

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(client_agent_runner, "_run_client_agent_once", fake_run_once)
    monkeypatch.setattr(client_agent_runner, "_reconnect_sleep_seconds", lambda delay: delay + 0.5)
    monkeypatch.setattr(client_agent_runner.asyncio, "sleep", fake_sleep)

    config = ClientAgentConfig(
        client_id=client_id,
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=Path("/opt/web-terminal-acp-client"),
    )

    await client_agent_runner.run_client_agent(config)

    assert sleeps == [1.5, 2.5]
