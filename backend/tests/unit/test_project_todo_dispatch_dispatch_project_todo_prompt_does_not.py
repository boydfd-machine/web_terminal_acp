from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.workspace.application import project_todo_dispatch
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.models import ClientRuntime


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return False

@pytest.mark.asyncio
async def test_dispatch_project_todo_prompt_does_not_schedule_summary_for_compose(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    scheduled = False

    async def fake_wait_for_runtime_window(**_kwargs):
        return ClientRuntime.local, RuntimeWindow(
            session_id="session",
            window_id="1",
            cwd="/workspace/project",
            shell_command="codex",
        )

    async def fake_wait_for_agent_terminal_ready(*_args, **_kwargs):
        return None

    async def fake_schedule_summary_after_submitted_todo_prompt(**_kwargs):
        nonlocal scheduled
        scheduled = True

    async def fake_wait_for_agent_working(**_kwargs):
        raise AssertionError("compose dispatch should not wait for agent work")

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def capture_output_bytes(self, *_args, **_kwargs):
            return b""

        async def send_input_direct(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(project_todo_dispatch, "_wait_for_runtime_window", fake_wait_for_runtime_window)
    monkeypatch.setattr(project_todo_dispatch, "_wait_for_agent_terminal_ready", fake_wait_for_agent_terminal_ready)
    monkeypatch.setattr(
        project_todo_dispatch,
        "_schedule_summary_after_submitted_todo_prompt",
        fake_schedule_summary_after_submitted_todo_prompt,
    )
    monkeypatch.setattr(project_todo_dispatch, "_wait_for_agent_working", fake_wait_for_agent_working)
    monkeypatch.setattr(project_todo_dispatch, "TerminalBroker", FakeBroker)

    await project_todo_dispatch.dispatch_project_todo_prompt(
        client_id=client_id,
        window_id=window_id,
        prompt="todo prompt",
        submit_prompt=False,
        session_factory=lambda: None,
        tmux_manager=None,
        registry=None,
    )

    assert scheduled is False


@pytest.mark.asyncio
async def test_dispatch_project_todo_prompt_retries_claude_enter_while_waiting(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    sent_inputs: list[bytes] = []

    async def fake_wait_for_runtime_window(**_kwargs):
        return ClientRuntime.local, RuntimeWindow(
            session_id="session",
            window_id="1",
            cwd="/workspace/project",
            shell_command="claude",
        )

    async def fake_wait_for_agent_terminal_ready(*_args, **_kwargs):
        return None

    async def fake_schedule_summary_after_submitted_todo_prompt(**_kwargs):
        return None

    async def fake_load_work_status(*_args, **_kwargs):
        return SimpleNamespace(state="RECENT_ACTIVE")

    async def fake_get_window_for_client(*_args, **_kwargs):
        return SimpleNamespace(terminal_last_output_at=datetime.now(UTC))

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def capture_output_bytes(self, *_args, **_kwargs):
            return b""

        async def send_input_direct(self, _client_id, _window_id, _runtime_window, data):
            sent_inputs.append(data)

    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_FOLLOWUP_SUBMIT_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_FOLLOWUP_SUBMIT_DURATION_SECONDS", 1.0)
    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(project_todo_dispatch, "_wait_for_runtime_window", fake_wait_for_runtime_window)
    monkeypatch.setattr(project_todo_dispatch, "_wait_for_agent_terminal_ready", fake_wait_for_agent_terminal_ready)
    monkeypatch.setattr(project_todo_dispatch, "load_work_status", fake_load_work_status)
    monkeypatch.setattr(project_todo_dispatch, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(
        project_todo_dispatch,
        "_schedule_summary_after_submitted_todo_prompt",
        fake_schedule_summary_after_submitted_todo_prompt,
    )
    monkeypatch.setattr(project_todo_dispatch, "TerminalBroker", FakeBroker)

    await project_todo_dispatch.dispatch_project_todo_prompt(
        client_id=client_id,
        window_id=window_id,
        prompt="todo prompt",
        submit_prompt=True,
        session_factory=FakeSessionContext,
        tmux_manager=None,
        registry=None,
    )

    assert sent_inputs[0] == b"\x1b[200~todo prompt\x1b[201~\n"
    assert len(sent_inputs) >= 2
    assert all(data == b"\n" for data in sent_inputs[1:])
