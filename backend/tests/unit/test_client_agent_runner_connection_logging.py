from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import UUID

import pytest

from app.client_agent.config import ClientAgentConfig
from app.client_agent.runner import _run_cleanup_step
from app.client_agent.runner.bulk_receive import receive_control_message
import app.client_agent.runner as client_agent_runner
import app.client_agent.runner.bulk_receive as bulk_receive


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.mark.asyncio
async def test_expected_reconnect_logs_without_warning_traceback(monkeypatch, caplog) -> None:
    attempts = 0

    async def fake_run_once(config: ClientAgentConfig) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("Multiple exceptions: Connect call failed ('127.0.0.1', 5173)")
        return True

    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(client_agent_runner, "_run_client_agent_once", fake_run_once)
    monkeypatch.setattr(client_agent_runner.asyncio, "sleep", fake_sleep)

    config = ClientAgentConfig(
        client_id=CLIENT_ID,
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=Path("/opt/web-terminal-acp-client"),
    )

    with caplog.at_level(logging.WARNING):
        await client_agent_runner.run_client_agent(config)

    assert "client-agent connection failed; reconnecting" not in caplog.text


@pytest.mark.asyncio
async def test_cleanup_step_suppresses_expected_connection_close_warning(caplog) -> None:
    async def closed_connection() -> None:
        raise OSError("Multiple exceptions: Connect call failed ('127.0.0.1', 5173)")

    with caplog.at_level(logging.WARNING):
        await _run_cleanup_step(
            "websocket.close",
            closed_connection(),
            client_id=CLIENT_ID,
            timeout_seconds=0.1,
        )

    assert "client-agent cleanup step failed" not in caplog.text


@pytest.mark.asyncio
async def test_receive_control_message_consumes_control_exception_when_bulk_stops(monkeypatch) -> None:
    created_tasks: list[asyncio.Task] = []
    original_create_task = asyncio.create_task
    ready = asyncio.Event()

    class ClosedControlWebSocket:
        async def recv(self) -> str:
            await ready.wait()
            raise RuntimeError("control websocket closed")

    async def stopped_bulk_loop() -> None:
        await ready.wait()
        raise RuntimeError("bulk websocket stopped")

    def tracking_create_task(coro):
        task = original_create_task(coro)
        created_tasks.append(task)
        return task

    bulk_receive_task = asyncio.create_task(stopped_bulk_loop())
    monkeypatch.setattr(bulk_receive.asyncio, "create_task", tracking_create_task)
    ready.set()
    with pytest.raises(RuntimeError, match="bulk websocket stopped"):
        await receive_control_message(ClosedControlWebSocket(), bulk_receive_task)

    control_recv_task = created_tasks[0]
    assert not getattr(control_recv_task, "_log_traceback", False)
