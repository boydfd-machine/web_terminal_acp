# ruff: noqa: F403, F405
from tests.unit.test_terminal_artifact_service_support import *
from app.contexts.terminal_artifacts.application.terminal_execution import _command_bytes_for_prompt

from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus

@pytest.mark.asyncio
async def test_artifact_collector_waits_until_output_matches_predicate() -> None:
    collector = _ArtifactOutputCollector()

    async def feed_later() -> None:
        await collector.feed(b"thinking")
        await collector.feed(b'{"task":"demo","goals":[],"nodes":[],"edges":[]}')

    await feed_later()

    output = await collector.wait_for_match(
        lambda value: '"task":"demo"' in value,
        timeout_seconds=1,
        idle_seconds=0,
    )

    assert '"task":"demo"' in output

def test_agent_terminal_ready_detection_waits_for_codex_prompt() -> None:
    loading = """
╭────────────╮
│ >_ OpenAI Codex (v0.136.0)
│ model:       loading   /model to change
╰────────────╯
"""
    ready = """
╭────────────╮
│ >_ OpenAI Codex (v0.136.0)
│ model:       gpt-5.5 xhigh   /model to change
╰────────────╯

› Improve documentation in @filename
"""

    assert not _agent_terminal_is_ready("codex", loading)
    assert _agent_terminal_is_ready("codex", ready)
    assert _agent_terminal_is_ready(
        "codex",
        "OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n›\n",
    )
    assert _agent_terminal_is_ready("codex", "OpenAI Codex\n\n›\n")

def test_agent_terminal_ready_detection_waits_for_claude_prompt() -> None:
    assert not _agent_terminal_is_ready("claude_code", "Claude Code v2.1.150\nStarting...")
    assert _agent_terminal_is_ready("claude_code", "Claude Code v2.1.150\n❯ ")
    assert _agent_terminal_is_ready(
        "claude_code",
        'Claude Code v2.1.150\n❯\xa0Try "fix typecheck errors"\n',
    )

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

    assert not _agent_terminal_is_ready("cursor_cli", loading)
    assert _agent_terminal_is_ready("cursor_cli", ready)


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

    assert not _agent_terminal_is_ready("cursor_cli", loading)
    assert _agent_terminal_is_ready("cursor_cli", ready)

def test_agent_terminal_ready_detection_does_not_depend_on_antigravity_account_or_model() -> None:
    assert not _agent_terminal_is_ready("antigravity_cli", "Antigravity CLI\nSigning in...\n")
    assert not _agent_terminal_is_ready("antigravity_cli", "Antigravity CLI\nLoading conversation...\n")
    assert _agent_terminal_is_ready("antigravity_cli", "Antigravity CLI\n\n> \n")
    assert _agent_terminal_is_ready("antigravity_cli", "Antigravity\n\n›\n")
    assert _agent_terminal_is_ready("antigravity_cli", "Antigravity CLI\n\n` Type your task\n")


def test_artifact_prompt_dispatch_uses_antigravity_bracketed_paste_and_composer_submit() -> None:
    assert _command_bytes_for_prompt("agy-p", "line one\nline two") == (
        b"\x1b[200~line one\nline two\x1b[201~\x1b[13u"
    )

def test_artifact_terminal_retention_uses_metadata_with_bounds() -> None:
    assert _artifact_terminal_retention_seconds({"terminal_retention_seconds": 120}) == 120.0
    assert _artifact_terminal_retention_seconds({"terminal_retention_seconds": 7200}) == 3600.0
    assert _artifact_terminal_retention_seconds({"terminal_retention_seconds": -1}) == 600.0
    assert _artifact_terminal_retention_seconds({"terminal_retention_seconds": True}) == 600.0

def test_artifact_prompt_with_output_language_preserves_schema_keys_instruction() -> None:
    prompt = _artifact_prompt_with_output_language(
        'Output only JSON with shape: {"title": "...", "cards": []}.',
        "English",
    )

    assert prompt.startswith("System language for artifact output: English.")
    assert "Write all user-facing artifact content in this language." in prompt
    assert "keep object keys" in prompt
    assert "enum/const values" in prompt
    assert 'Output only JSON with shape: {"title": "...", "cards": []}.' in prompt

@pytest.mark.asyncio
async def test_wait_before_ephemeral_window_cleanup_sleeps_for_retention(monkeypatch) -> None:
    calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(terminal_artifact_service.asyncio, "sleep", fake_sleep)

    await _wait_before_ephemeral_window_cleanup(120)
    await _wait_before_ephemeral_window_cleanup(0)

    assert calls == [120]

@pytest.mark.asyncio
async def test_mark_generation_failed_marks_artifact_and_publishes_invalidation() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    events = []

    class FakeUiEventHub:
        async def publish_invalidation(self, resources, *, client_id, window_id, reason):
            events.append((resources, client_id, window_id, reason))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            client, _token = await create_client(session, name="remote", runtime=ClientRuntime.remote)
            window = await create_window(session, client.id, cwd="/tmp", shell_command="codex")
            artifact = await create_terminal_artifact(
                session,
                client_id=client.id,
                virtual_window_id=window.id,
                artifact_kind="agent_trace_graph",
                title="Trace",
            )
            await session.commit()
            request = TerminalArtifactGenerationRequest(
                client_id=client.id,
                window_id=window.id,
                artifact_id=artifact.id,
            )

        await _mark_generation_failed(
            request,
            error="artifact generation timed out",
            session_factory=session_factory,
            ui_event_hub=FakeUiEventHub(),
        )

        async with session_factory() as session:
            failed_artifact = await session.get(TerminalArtifact, artifact.id)
            assert failed_artifact.status is TerminalArtifactStatus.failed
            assert failed_artifact.last_error == "artifact generation timed out"
        assert events == [
            (
                ["terminal_artifacts", "project_todos"],
                client.id,
                window.id,
                "artifact_failed",
            )
        ]
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_cleanup_ephemeral_window_kills_runtime_when_db_window_was_rolled_back(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    ephemeral_window_id = uuid4()
    events = []

    class FakeRemoteRuntime:
        def __init__(self, **kwargs):
            events.append(("runtime", kwargs["client_id"], kwargs["request_timeout"]))

        async def kill_window(self, *, window_id, remote_session_id=None, remote_window_id=None):
            events.append(("kill", window_id, remote_session_id, remote_window_id))

    monkeypatch.setattr(terminal_artifact_service, "RemoteRuntime", FakeRemoteRuntime)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            client, _token = await create_client(session, name="remote", runtime=ClientRuntime.remote)
            await session.commit()

        await _cleanup_ephemeral_window(
            client.id,
            ephemeral_window_id,
            session_factory=session_factory,
            tmux_manager=object(),
            registry=object(),
            runtime_window=RuntimeWindow(session_id="remote-session", window_id="@77"),
        )

        assert events == [
            ("runtime", client.id, 10.0),
            ("kill", ephemeral_window_id, "remote-session", "@77"),
        ]
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_reconcile_interrupted_terminal_artifacts_marks_incomplete_failed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            client, _token = await create_client(session, name="remote", runtime=ClientRuntime.remote)
            window = await create_window(session, client.id, cwd="/tmp", shell_command="codex")
            pending = await create_terminal_artifact(
                session,
                client_id=client.id,
                virtual_window_id=window.id,
                artifact_kind="agent_trace_graph",
                title="Pending",
            )
            running = await create_terminal_artifact(
                session,
                client_id=client.id,
                virtual_window_id=window.id,
                artifact_kind="agent_trace_graph",
                title="Running",
            )
            succeeded = await create_terminal_artifact(
                session,
                client_id=client.id,
                virtual_window_id=window.id,
                artifact_kind="agent_trace_graph",
                title="Succeeded",
            )
            ephemeral = await create_window(
                session,
                client.id,
                cwd="/tmp",
                shell_command="codex",
                parent_window_id=window.id,
                derived_mode="ephemeral",
            )
            running.status = TerminalArtifactStatus.running
            running.ephemeral_window_id = ephemeral.id
            succeeded.status = TerminalArtifactStatus.succeeded
            await session.commit()

            changed_count = await reconcile_interrupted_terminal_artifacts(session)
            await session.commit()

            assert changed_count == 2
            assert pending.status is TerminalArtifactStatus.failed
            assert running.status is TerminalArtifactStatus.failed
            assert running.ephemeral_window_id is None
            assert "interrupted" in (running.last_error or "")
            assert succeeded.status is TerminalArtifactStatus.succeeded
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_reconcile_interrupted_terminal_artifacts_preserves_pending_project_todo_artifacts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            client, _token = await create_client(session, name="local")
            window = await create_window(session, client.id, cwd="/tmp", shell_command="codex")
            todo = ProjectTodo(
                client_id=client.id,
                project_path="/tmp",
                title="Needs artifact dispatch",
                status=ProjectTodoStatus.dispatched,
                assigned_window_id=window.id,
                artifact_kinds_json=["agent_trace_graph"],
            )
            session.add(todo)
            await session.flush()
            artifact = await create_terminal_artifact(
                session,
                client_id=client.id,
                virtual_window_id=window.id,
                source_window_id=window.id,
                artifact_kind="agent_trace_graph",
                title="Pending todo artifact",
                metadata_json={
                    "project_todo_id": str(todo.id),
                    "purpose": "todo_artifact",
                    "artifact_scope": "terminal",
                },
            )
            session.add(
                ProjectTodoArtifact(
                    project_todo_id=todo.id,
                    terminal_artifact_id=artifact.id,
                    created_by_window_id=window.id,
                    purpose="todo_artifact",
                )
            )
            await session.commit()

            changed_count = await reconcile_interrupted_terminal_artifacts(session)
            await session.commit()

            assert changed_count == 0
            assert artifact.status is TerminalArtifactStatus.pending
            assert artifact.last_error is None
            assert todo.status is ProjectTodoStatus.dispatched
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_run_artifact_prompt_waits_for_agent_ready_before_sending(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_SETTLE_SECONDS", 0.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_IDLE_GRACE_SECONDS", 0.0)
    events = []

    class FakeBroker:
        def __init__(self):
            self.capture_count = 0

        def runtime_for(self, client_id):
            return object()

        async def subscribe(self, client_id, window_id, sender):
            raise AssertionError("artifact generation must not add a broker output subscription")

        async def attach(self, client_id, window_id, runtime_window, *, view_id):
            raise AssertionError("artifact generation must not attach a hidden terminal view")

        async def resize(self, *args, **kwargs):
            raise AssertionError("artifact generation must not resize a hidden terminal view")

        async def capture_output_bytes(self, client_id, window_id, runtime_window, *, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            self.capture_count += 1
            if self.capture_count == 1:
                return b"codex --dangerously-bypass-approvals-and-sandbox resume session\nmodel:       loading\n"
            events.append(("ready", None))
            if any(event[0] == "send" for event in events):
                return (
                    b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "
                    b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'
                )
            return b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "

        async def send_input_direct(self, client_id, window_id, runtime_window, data):
            events.append(("send", data.decode("utf-8")))

        async def unsubscribe(self, *args, **kwargs):
            raise AssertionError("artifact generation must not unsubscribe a broker output subscription")

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type("Window", (), {"shell_command": "codex"})()
    ephemeral_window = type("Window", (), {"id": uuid4()})()
    runtime_window = type("RuntimeWindow", (), {})()

    output = await _run_artifact_prompt(
        client,
        source_window,
        ephemeral_window,
        runtime_window,
        "artifact prompt",
        output_path=None,
        is_complete=lambda value: '"task":"demo"' in value,
        session_factory=unused_session_factory,
        terminal_broker=FakeBroker(),
        tmux_manager=object(),
        registry=None,
    )

    assert '"task":"demo"' in output
    assert [event[0] for event in events].index("ready") < [event[0] for event in events].index("send")
    assert events[[event[0] for event in events].index("send")][1] == "artifact prompt\x1b[13u"

@pytest.mark.asyncio
async def test_run_artifact_prompt_reads_json_from_output_file(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_SETTLE_SECONDS", 0.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_FILE_POLL_INTERVAL_SECONDS", 0.01)
    events = []

    class FakeBroker:
        def runtime_for(self, client_id):
            return object()

        async def capture_output_bytes(self, client_id, window_id, runtime_window, *, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            return b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "

        async def send_input_direct(self, client_id, window_id, runtime_window, data):
            events.append(("send", data.decode("utf-8")))

        async def read_file_bytes(self, client_id, path, *, max_bytes=None):
            events.append(("read_file", path, max_bytes))
            if any(event[0] == "send" for event in events):
                return b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'
            raise FileNotFoundError(path)

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type("Window", (), {"shell_command": "codex"})()
    ephemeral_window = type("Window", (), {"id": uuid4()})()
    runtime_window = type("RuntimeWindow", (), {})()

    output = await _run_artifact_prompt(
        client,
        source_window,
        ephemeral_window,
        runtime_window,
        "artifact prompt",
        output_path="/tmp/web-terminal-artifact.json",
        is_complete=lambda value: '"task":"demo"' in value,
        session_factory=unused_session_factory,
        terminal_broker=FakeBroker(),
        tmux_manager=object(),
        registry=None,
    )

    assert output == '{"task":"demo","goals":[],"nodes":[],"edges":[]}'
    assert events[0][0] == "send"
    assert "artifact prompt\x1b[13u" == events[0][1]
    assert any(event[0] == "read_file" for event in events)
