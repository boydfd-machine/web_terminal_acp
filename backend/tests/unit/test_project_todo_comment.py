from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.workspace.application import project_todo_comment
from app.contexts.workspace.application import project_todo_comment_readiness
from app.models import ClientRuntime


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return False


def test_build_project_todo_comment_prompt() -> None:
    prompt = project_todo_comment.build_project_todo_comment_prompt(
        project_path="/workspace/project",
        title="Fix dispatch",
        comment="Please check the resume path.",
    )

    assert "follow-up comment" in prompt
    assert "Project path: /workspace/project" in prompt
    assert "Todo: Fix dispatch" in prompt
    assert "Comment:\nPlease check the resume path." in prompt
    assert "Address this comment in the current session" in prompt


def test_comment_agent_prompt_detection_accepts_current_claude_prompt() -> None:
    output = 'Claude Code v2.1.150\n❯\xa0Try "fix typecheck errors"\n'

    assert project_todo_comment_readiness._comment_agent_is_current_prompt("claude_code", output)


@pytest.mark.asyncio
async def test_submit_comment_prompt_hidden_attach_recovers_and_sends(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    original_runtime_window = RuntimeWindow(
        session_id="old-session",
        window_id="@1",
        cwd="/workspace/project",
        shell_command="codex",
    )
    refreshed_runtime_window = RuntimeWindow(
        session_id="new-session",
        window_id="@8",
        cwd="/workspace/project",
        shell_command="codex",
    )
    sent_inputs: list[bytes] = []
    attached_view_ids: list[str] = []
    detached_view_ids: list[str] = []
    persisted: list[RuntimeWindow] = []
    ready_capture_output = None
    working_windows: list[str] = []
    scheduled_windows: list[str] = []

    async def fake_wait_for_comment_agent_terminal_ready(**kwargs):
        nonlocal ready_capture_output
        ready_capture_output = kwargs["capture_output"]
        assert await kwargs["capture_output"]() == b"agent ready"

    async def fake_wait_for_agent_working(**kwargs):
        working_windows.append(str(kwargs["window_id"]))

    async def fake_schedule_summary_after_submitted_todo_prompt(**kwargs):
        scheduled_windows.append(str(kwargs["window_id"]))

    async def fake_persist_comment_runtime_window(**kwargs):
        persisted.append(kwargs["binding"].runtime_window)

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def attach(self, _client_id, _window_id, runtime_window, *, output_callback=None, view_id=None):
            assert runtime_window == original_runtime_window
            assert output_callback is not None
            assert view_id is not None
            attached_view_ids.append(str(view_id))
            await output_callback(b"attached output")
            return refreshed_runtime_window

        async def capture_output_bytes(self, _client_id, _window_id, runtime_window, *, view_id=None, history_lines):
            assert runtime_window == refreshed_runtime_window
            assert view_id is not None
            assert str(view_id) == attached_view_ids[0]
            assert history_lines == project_todo_comment.PROJECT_TODO_CAPTURE_HISTORY_LINES
            return b"agent ready"

        async def send_input_direct(self, _client_id, _window_id, runtime_window, data):
            assert runtime_window == refreshed_runtime_window
            sent_inputs.append(data)

        async def unsubscribe(self, _client_id, view_id, _sender):
            detached_view_ids.append(str(view_id))

    monkeypatch.setattr(project_todo_comment, "TerminalBroker", FakeBroker)
    monkeypatch.setattr(
        project_todo_comment,
        "wait_for_comment_agent_terminal_ready",
        fake_wait_for_comment_agent_terminal_ready,
    )
    monkeypatch.setattr(project_todo_comment, "_wait_for_agent_working", fake_wait_for_agent_working)
    monkeypatch.setattr(
        project_todo_comment,
        "_schedule_summary_after_submitted_todo_prompt",
        fake_schedule_summary_after_submitted_todo_prompt,
    )
    monkeypatch.setattr(project_todo_comment, "_persist_comment_runtime_window", fake_persist_comment_runtime_window)

    await project_todo_comment._submit_comment_prompt(
        client=SimpleNamespace(id=client_id, runtime=ClientRuntime.local),
        window=SimpleNamespace(
            id=window_id,
            tmux_session=original_runtime_window.session_id,
            tmux_window_id=original_runtime_window.window_id,
            tmux_window_index=None,
            remote_session_id=None,
            remote_window_id=None,
            cwd=original_runtime_window.cwd,
            shell_command=original_runtime_window.shell_command,
        ),
        prompt="follow up",
        tmux_manager=object(),
        registry=None,
        session_factory=FakeSessionContext,
    )

    assert ready_capture_output is not None
    assert sent_inputs == [b"\x1b[200~follow up\x1b[201~\x1b[13u"]
    assert persisted == [refreshed_runtime_window]
    assert working_windows == [str(window_id)]
    assert scheduled_windows == [str(window_id)]
    assert attached_view_ids == detached_view_ids


@pytest.mark.asyncio
async def test_submit_comment_prompt_uses_latest_agent_session_when_shell_command_is_generic(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    runtime_window = RuntimeWindow(
        session_id="web-terminal",
        window_id="@3",
        cwd="/workspace/project",
        shell_command="/bin/bash",
    )
    sent_inputs: list[bytes] = []
    ready_shell_commands: list[str | None] = []
    codex_ready_output = ">_ Codex\n› ".encode()

    async def fake_agent_provider_for_window(_session, requested_window):
        assert requested_window.id == window_id
        return "codex"

    async def fake_wait_for_comment_agent_terminal_ready(**kwargs):
        ready_shell_commands.append(kwargs["prompt_shell_command"])
        assert await kwargs["capture_output"]() == codex_ready_output

    async def fake_wait_for_agent_working(**_kwargs):
        return None

    async def fake_schedule_summary_after_submitted_todo_prompt(**_kwargs):
        return None

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def attach(self, _client_id, _window_id, attached_window, *, output_callback=None, view_id=None):
            assert attached_window == runtime_window
            return runtime_window

        async def capture_output_bytes(self, *_args, **_kwargs):
            return codex_ready_output

        async def send_input_direct(self, _client_id, _window_id, attached_window, data):
            assert attached_window == runtime_window
            sent_inputs.append(data)

        async def unsubscribe(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(project_todo_comment, "TerminalBroker", FakeBroker)
    monkeypatch.setattr(project_todo_comment, "_agent_provider_for_window", fake_agent_provider_for_window)
    monkeypatch.setattr(
        project_todo_comment,
        "wait_for_comment_agent_terminal_ready",
        fake_wait_for_comment_agent_terminal_ready,
    )
    monkeypatch.setattr(project_todo_comment, "_wait_for_agent_working", fake_wait_for_agent_working)
    monkeypatch.setattr(
        project_todo_comment,
        "_schedule_summary_after_submitted_todo_prompt",
        fake_schedule_summary_after_submitted_todo_prompt,
    )

    await project_todo_comment._submit_comment_prompt(
        client=SimpleNamespace(id=client_id, runtime=ClientRuntime.local),
        window=SimpleNamespace(
            id=window_id,
            tmux_session=runtime_window.session_id,
            tmux_window_id=runtime_window.window_id,
            tmux_window_index=None,
            remote_session_id=None,
            remote_window_id=None,
            cwd=runtime_window.cwd,
            shell_command=runtime_window.shell_command,
        ),
        prompt="follow up",
        tmux_manager=object(),
        registry=None,
        session_factory=FakeSessionContext,
    )

    assert ready_shell_commands == ["codex"]
    assert sent_inputs == [b"\x1b[200~follow up\x1b[201~\x1b[13u"]


@pytest.mark.asyncio
async def test_submit_comment_prompt_relaunches_agent_when_terminal_is_shell_prompt(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    runtime_window = RuntimeWindow(
        session_id="web-terminal",
        window_id="@9",
        cwd="/workspace/project",
        shell_command="codex",
    )
    captured_outputs = [
        b">_ Codex\n\xe2\x80\xba \n\n\xe2\x9e\x9c  web_terminal_acp git:(main)\n",
        b">_ Codex\n\xe2\x80\xba ",
    ]
    sent_inputs: list[bytes] = []

    async def fake_wait_for_agent_working(**_kwargs):
        return None

    async def fake_schedule_summary_after_submitted_todo_prompt(**_kwargs):
        return None

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def attach(self, _client_id, _window_id, attached_window, *, output_callback=None, view_id=None):
            assert attached_window == runtime_window
            return runtime_window

        async def capture_output_bytes(self, *_args, **_kwargs):
            return captured_outputs.pop(0)

        async def send_input_direct(self, _client_id, _window_id, attached_window, data):
            assert attached_window == runtime_window
            sent_inputs.append(data)

        async def unsubscribe(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(project_todo_comment, "TerminalBroker", FakeBroker)
    monkeypatch.setattr(project_todo_comment, "_wait_for_agent_working", fake_wait_for_agent_working)
    monkeypatch.setattr(
        project_todo_comment,
        "_schedule_summary_after_submitted_todo_prompt",
        fake_schedule_summary_after_submitted_todo_prompt,
    )

    await project_todo_comment._submit_comment_prompt(
        client=SimpleNamespace(id=client_id, runtime=ClientRuntime.local),
        window=SimpleNamespace(
            id=window_id,
            tmux_session=runtime_window.session_id,
            tmux_window_id=runtime_window.window_id,
            tmux_window_index=None,
            remote_session_id=None,
            remote_window_id=None,
            cwd=runtime_window.cwd,
            shell_command=runtime_window.shell_command,
        ),
        prompt="follow up",
        tmux_manager=object(),
        registry=None,
        session_factory=FakeSessionContext,
    )

    assert captured_outputs == []
    assert sent_inputs == [
        b"cd /workspace/project && codex --dangerously-bypass-approvals-and-sandbox\n",
        b"\x1b[200~follow up\x1b[201~\x1b[13u",
    ]
