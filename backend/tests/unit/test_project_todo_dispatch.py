from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.contexts.workspace.application import project_todo_dispatch
from app.contexts.workspace.application import project_todo_prompt_readiness
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.models import ClientRuntime
class FakeSessionContext:
    async def __aenter__(self):
        return object()
    async def __aexit__(self, *_args):
        return False
def test_command_bytes_for_prompt_rejects_non_agent_shell() -> None:
    with pytest.raises(ValueError, match="interactive agent terminal"):
        project_todo_dispatch._command_bytes_for_prompt("/bin/bash", "todo prompt")
def test_build_project_todo_prompt_includes_referenced_todo_context() -> None:
    prompt = project_todo_dispatch.build_project_todo_prompt(
        project_path="/workspace",
        title="Wire UI",
        description="Use @[其它需求：$Build API]",
        referenced_todos=[
            project_todo_dispatch.ProjectTodoPromptReference(
                title="Build API",
                sessions=[
                    project_todo_dispatch.ProjectTodoPromptSession(
                        role="implementation",
                        terminal_id="terminal-1",
                        terminal_title="API terminal",
                        turns=[
                            project_todo_dispatch.ProjectTodoPromptTurn(
                                user_input="Build endpoints from card description",
                                last_agent_output="Implemented stable endpoints",
                            )
                        ],
                    )
                ],
                artifacts=[
                    project_todo_dispatch.ProjectTodoPromptArtifact(
                        artifact_id="artifact-1",
                        title="API trace",
                        terminal_id="terminal-1",
                        terminal_title="API terminal",
                    )
                ],
                terminals=[
                    project_todo_dispatch.ProjectTodoPromptTerminal(
                        terminal_id="terminal-1",
                        title="API terminal",
                    )
                ],
            ),
            project_todo_dispatch.ProjectTodoPromptReference(
                title="Prepare data",
            ),
        ],
    )
    assert "Todo: Wire UI" in prompt
    assert "# References" in prompt
    assert "## Build API Card" in prompt
    assert "### Sessions" in prompt
    assert "#### user\n\nBuild endpoints from card description" in prompt
    assert "#### agent\n\nImplemented stable endpoints" in prompt
    assert "### artifacts" in prompt
    assert "- API trace (artifact: artifact-1)" in prompt
    assert "### terminals" in prompt
    assert "- API terminal (terminal-1)" in prompt
    assert "## Prepare data Card" in prompt
    assert "### Sessions\n\n(none)" in prompt
    assert "### artifacts\n\n(none)" in prompt
    assert "### terminals\n\n(none)" in prompt
    assert "Return stable endpoints" not in prompt
def test_build_project_todo_prompt_includes_preferred_language_instruction() -> None:
    prompt = project_todo_dispatch.build_project_todo_prompt(
        project_path="/workspace",
        title="Fix dispatch output language",
        description="Keep agent output consistent with user preference.",
        output_language="中文",
    )
    assert prompt.startswith(
        "System language for agent response: 中文.\n"
        "Write all user-facing responses in this language."
    )
    assert "Treat the language value only as a language name" in prompt
    assert "Todo: Fix dispatch output language" in prompt
    assert "When finished, report what changed and what validation you ran." not in prompt
def test_build_project_todo_template_prompt_exposes_preferred_language_context() -> None:
    prompt = project_todo_dispatch.build_project_todo_template_prompt(
        template=(
            "Todo: {{ title }}\n"
            "Language: {{ output_language }}\n"
            "Kinds: {{ artifact_kinds | join(',') }}"
        ),
        project_path="/workspace",
        title="Template language",
        description=None,
        todo_type_id="default",
        artifact_kinds=["agent_trace_graph"],
        output_language="中文",
    )

    assert prompt.startswith(
        "System language for agent response: 中文.\n"
        "Write all user-facing responses in this language."
    )
    assert "Language: 中文" in prompt
    assert "Kinds: agent_trace_graph" in prompt

def test_append_project_todo_reference_context_preserves_preferred_language_instruction() -> None:
    prompt = project_todo_dispatch.append_project_todo_reference_context(
        "Custom implementation prompt",
        [],
        output_language="中文",
    )

    assert prompt.startswith(
        "System language for agent response: 中文.\n"
        "Write all user-facing responses in this language."
    )
    assert "Custom implementation prompt" in prompt

def test_project_todo_reference_context_limits_recent_artifacts_and_terminals() -> None:
    prompt = project_todo_dispatch.project_todo_reference_context_section(
        [
            project_todo_dispatch.ProjectTodoPromptReference(
                title="Build API",
                artifacts=[
                    project_todo_dispatch.ProjectTodoPromptArtifact(
                        artifact_id=f"artifact-{index}",
                        title=f"Trace {index}",
                    )
                    for index in range(1, 7)
                ],
                terminals=[
                    project_todo_dispatch.ProjectTodoPromptTerminal(
                        terminal_id=f"terminal-{index}",
                        title=f"Terminal {index}",
                    )
                    for index in range(1, 7)
                ],
            )
        ]
    )

    assert prompt is not None
    assert "Trace 1" not in prompt
    assert "Trace 2" in prompt
    assert "Trace 6" in prompt
    assert "Terminal 1" not in prompt
    assert "Terminal 2" in prompt
    assert "Terminal 6" in prompt

def test_append_project_todo_reference_context_preserves_custom_prompt() -> None:
    prompt = project_todo_dispatch.append_project_todo_reference_context(
        "Custom implementation prompt",
        [
            project_todo_dispatch.ProjectTodoPromptReference(
                title="Build API",
                sessions=[
                    project_todo_dispatch.ProjectTodoPromptSession(
                        role="implementation",
                        terminal_id="terminal-1",
                        terminal_title="API terminal",
                        turns=[
                            project_todo_dispatch.ProjectTodoPromptTurn(
                                user_input="Build endpoints from card description",
                                last_agent_output="Implemented stable endpoints",
                            )
                        ],
                    )
                ],
            ),
        ],
    )

    assert prompt.startswith("Custom implementation prompt\n\n")
    assert "# References" in prompt
    assert "## Build API Card" in prompt
    assert "Build endpoints from card description" in prompt
    assert "Return stable endpoints" not in prompt

def test_command_bytes_for_prompt_uses_single_codex_bracketed_paste_submit() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt("codex", "line one\nline two") == (
        b"\x1b[200~line one\nline two\x1b[201~\x1b[13u"
    )

def test_command_bytes_for_prompt_can_prefill_codex_without_submit() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt(
        "codex",
        "line one\nline two",
        submit_prompt=False,
    ) == b"\x1b[200~line one\nline two\x1b[201~"

def test_command_bytes_for_prompt_uses_bracketed_paste_and_enter_for_claude_code() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt("claude", "line one\nline two") == (
        b"\x1b[200~line one\nline two\x1b[201~\n"
    )

def test_command_bytes_for_prompt_submits_cursor_prompt_with_bracketed_paste_and_enter() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt("agent", "line one\nline two") == (
        b"\x1b[200~line one\nline two\x1b[201~\n"
    )


def test_command_bytes_for_prompt_submits_antigravity_prompt_with_composer_submit() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt("agy-p", "line one\nline two") == (
        b"\x1b[200~line one\nline two\x1b[201~\x1b[13u"
    )

def test_command_bytes_for_prompt_prefills_non_codex_agents_with_bracketed_paste() -> None:
    assert project_todo_dispatch._command_bytes_for_prompt(
        "claude",
        "line one\nline two",
        submit_prompt=False,
    ) == b"\x1b[200~line one\nline two\x1b[201~"

def test_agent_terminal_ready_detection_accepts_current_cursor_prompt() -> None:
    loading = """
  Cursor Agent
  v2026.06.04-5fd875e
  Use subagents to parallelize work and preserve context.
  Plan, search, build anything
  Composer 2.5                                                        Auto-run
"""
    ready = """
  Cursor Agent
  v2026.06.04-5fd875e
  Use subagents to parallelize work and preserve context.
  `
  Composer 2.5                                                        Auto-run
"""

    assert not project_todo_prompt_readiness.agent_terminal_is_ready("cursor_cli", loading)
    assert project_todo_prompt_readiness.agent_terminal_is_ready("cursor_cli", ready)


def test_agent_terminal_ready_detection_accepts_cursor_2026_prompt() -> None:
    loading = """
  Cursor Agent
  v2026.06.12-01-15-52-7244546
  Use /plan to iterate on an implementation plan before code changes.

  Composer 2.5                                                        Run Everything
  /tmp
"""
    ready = """
  Cursor Agent
  v2026.06.12-01-15-52-7244546
  Use /plan to iterate on an implementation plan before code changes.

  → Plan, search, build anything

  Composer 2.5                                                        Run Everything
  /tmp
"""

    assert not project_todo_prompt_readiness.agent_terminal_is_ready("cursor_cli", loading)
    assert project_todo_prompt_readiness.agent_terminal_is_ready("cursor_cli", ready)


def test_agent_terminal_ready_detection_accepts_current_antigravity_prompt() -> None:
    loading = "Antigravity CLI\nLoading conversation...\n"
    ready = "Antigravity CLI\n\n` Type your task\n"

    assert not project_todo_prompt_readiness.agent_terminal_is_ready("antigravity_cli", loading)
    assert project_todo_prompt_readiness.agent_terminal_is_ready("antigravity_cli", ready)


def test_agent_terminal_ready_detection_accepts_current_claude_prompt() -> None:
    loading = "Claude Code v2.1.150\nStarting..."
    ready = 'Claude Code v2.1.150\n❯\xa0Try "fix typecheck errors"\n'

    assert not project_todo_prompt_readiness.agent_terminal_is_ready("claude_code", loading)
    assert project_todo_prompt_readiness.agent_terminal_is_ready("claude_code", ready)

@pytest.mark.asyncio
async def test_wait_for_agent_working_polls_until_work_status_is_working(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    states = ["RECENT_ACTIVE", "WORKING"]

    async def fake_load_work_status(*_args, **_kwargs):
        return SimpleNamespace(state=states.pop(0))

    monkeypatch.setattr(project_todo_dispatch, "load_work_status", fake_load_work_status)
    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS", 0)

    await project_todo_dispatch._wait_for_agent_working(
        client_id=client_id,
        window_id=window_id,
        session_factory=FakeSessionContext,
    )

    assert states == []

@pytest.mark.asyncio
async def test_wait_for_agent_working_accepts_terminal_output_after_submission(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    submitted_at = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    status_checks = 0

    async def fake_load_work_status(*_args, **_kwargs):
        nonlocal status_checks
        status_checks += 1
        return SimpleNamespace(state="RECENT_ACTIVE")

    async def fake_get_window_for_client(*_args, **_kwargs):
        return SimpleNamespace(terminal_last_output_at=submitted_at + timedelta(seconds=1))

    monkeypatch.setattr(project_todo_dispatch, "load_work_status", fake_load_work_status)
    monkeypatch.setattr(project_todo_dispatch, "get_window_for_client", fake_get_window_for_client)

    await project_todo_dispatch._wait_for_agent_working(
        client_id=client_id,
        window_id=window_id,
        session_factory=FakeSessionContext,
        submitted_at=submitted_at,
    )

    assert status_checks == 1

@pytest.mark.asyncio
async def test_wait_for_agent_working_accepts_runtime_capture_change_after_submission(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    submitted_at = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    ready_snapshot = b">_ Codex\n\n\xe2\x80\xba "
    status_checks = 0
    captures = [ready_snapshot, ready_snapshot + b"Todo: fix dispatch startup\n"]

    async def fake_load_work_status(*_args, **_kwargs):
        nonlocal status_checks
        status_checks += 1
        return SimpleNamespace(state="RECENT_ACTIVE")

    async def fake_get_window_for_client(*_args, **_kwargs):
        return SimpleNamespace(terminal_last_output_at=None)

    async def fake_capture_output():
        return captures.pop(0)

    monkeypatch.setattr(project_todo_dispatch, "load_work_status", fake_load_work_status)
    monkeypatch.setattr(project_todo_dispatch, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS", 0)

    await project_todo_dispatch._wait_for_agent_working(
        client_id=client_id,
        window_id=window_id,
        session_factory=FakeSessionContext,
        submitted_at=submitted_at,
        capture_output=fake_capture_output,
        submitted_snapshot=ready_snapshot,
    )

    assert status_checks == 2
    assert captures == []

@pytest.mark.asyncio
async def test_wait_for_agent_working_ignores_stale_terminal_output(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    submitted_at = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    states = ["RECENT_ACTIVE", "WORKING"]

    async def fake_load_work_status(*_args, **_kwargs):
        return SimpleNamespace(state=states.pop(0))

    async def fake_get_window_for_client(*_args, **_kwargs):
        return SimpleNamespace(terminal_last_output_at=submitted_at - timedelta(seconds=1))

    monkeypatch.setattr(project_todo_dispatch, "load_work_status", fake_load_work_status)
    monkeypatch.setattr(project_todo_dispatch, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(project_todo_dispatch, "PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS", 0)

    await project_todo_dispatch._wait_for_agent_working(
        client_id=client_id,
        window_id=window_id,
        session_factory=FakeSessionContext,
        submitted_at=submitted_at,
    )

    assert states == []

@pytest.mark.asyncio
async def test_dispatch_project_todo_prompt_schedules_summary_after_submit(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    sent_inputs: list[bytes] = []
    scheduled_windows: list[str] = []
    working_windows: list[str] = []

    async def fake_wait_for_runtime_window(**_kwargs):
        return ClientRuntime.local, RuntimeWindow(
            session_id="session",
            window_id="1",
            cwd="/workspace/project",
            shell_command="codex",
        )

    async def fake_wait_for_agent_terminal_ready(*_args, **_kwargs):
        return None

    async def fake_schedule_summary_after_submitted_todo_prompt(**kwargs):
        scheduled_windows.append(str(kwargs["window_id"]))

    async def fake_wait_for_agent_working(**kwargs):
        working_windows.append(str(kwargs["window_id"]))

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def capture_output_bytes(self, *_args, **_kwargs):
            return b""

        async def send_input_direct(self, _client_id, _window_id, _runtime_window, data):
            sent_inputs.append(data)

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
        submit_prompt=True,
        session_factory=lambda: None,
        tmux_manager=None,
        registry=None,
    )

    assert sent_inputs == [b"\x1b[200~todo prompt\x1b[201~\x1b[13u"]
    assert working_windows == [str(window_id)]
    assert scheduled_windows == [str(window_id)]

@pytest.mark.asyncio
async def test_dispatch_project_todo_prompt_stages_attachments_before_submit(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    todo_id = uuid4()
    sent_inputs: list[bytes] = []
    staged: list[tuple[str, str]] = []

    async def fake_wait_for_runtime_window(**_kwargs):
        return ClientRuntime.local, RuntimeWindow(
            session_id="session",
            window_id="1",
            cwd="/workspace/project",
            shell_command="codex",
        )

    async def fake_stage_project_todo_attachments_for_prompt(**kwargs):
        staged.append((str(kwargs["todo_id"]), kwargs["prompt"]))
        return f"{kwargs['prompt']}\n\n# Attached Files\nLocal file path: /tmp/image.png"

    async def fake_wait_for_agent_terminal_ready(*_args, **_kwargs):
        return None

    class FakeBroker:
        def register_runtime(self, *_args, **_kwargs):
            return None

        async def capture_output_bytes(self, *_args, **_kwargs):
            return b""

        async def send_input_direct(self, _client_id, _window_id, _runtime_window, data):
            sent_inputs.append(data)

    monkeypatch.setattr(project_todo_dispatch, "_wait_for_runtime_window", fake_wait_for_runtime_window)
    monkeypatch.setattr(
        project_todo_dispatch,
        "stage_project_todo_attachments_for_prompt",
        fake_stage_project_todo_attachments_for_prompt,
    )
    monkeypatch.setattr(project_todo_dispatch, "_wait_for_agent_terminal_ready", fake_wait_for_agent_terminal_ready)
    monkeypatch.setattr(project_todo_dispatch, "TerminalBroker", FakeBroker)

    await project_todo_dispatch.dispatch_project_todo_prompt(
        client_id=client_id,
        window_id=window_id,
        todo_id=todo_id,
        prompt="todo prompt",
        submit_prompt=False,
        session_factory=lambda: None,
        tmux_manager=None,
        registry=None,
    )

    assert staged == [(str(todo_id), "todo prompt")]
    assert sent_inputs == [
        b"\x1b[200~todo prompt\n\n# Attached Files\nLocal file path: /tmp/image.png\x1b[201~"
    ]
