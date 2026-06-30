# ruff: noqa: F403, F405
from tests.unit.test_client_agent_runner_support import *

@pytest.mark.asyncio
async def test_terminal_attach_existing_idle_tmux_window_resumes_recorded_session() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=True, pane_current_command="bash")

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreated == []
    assert supervisor.resume_calls == [(WINDOW_ID, False)]
    assert "resume_window" in calls
    assert writer.messages[-1].type == "terminal_attach_result"

@pytest.mark.asyncio
async def test_terminal_attach_existing_idle_tmux_window_without_record_does_not_resume() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=True, pane_current_command="bash")

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
            },
        ),
    )

    assert runtime.recreated == []
    assert supervisor.resume_calls == []
    assert "resume_window" not in calls
    assert writer.messages[-1].type == "terminal_attach_result"

@pytest.mark.asyncio
async def test_terminal_attach_does_not_recreate_missing_tmux_window_by_default() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    runtime = FakeRuntime(window_exists=False)

    with pytest.raises(RuntimeError, match="missing tmux window"):
        await handle_message_for_test(
            FakeWriter(),
            FakeBulkWriter(),
            object(),
            runtime,
            terminal,
            supervisor,
            FakeAgentToolWatcher(calls),
            {},
            {},
            AgentMessage(
                type="terminal_attach",
                client_id=UUID("12345678-1234-5678-1234-567812345678"),
                window_id=WINDOW_ID,
                request_id="request-1",
                payload={
                    "remote_session_id": "pool",
                    "remote_window_id": "@7",
                    "view_id": str(VIEW_ID),
                    "cwd": "/workspace/project",
                    "shell_command": "codex",
                },
            ),
        )

    assert runtime.recreated == []
    assert supervisor.resume_calls == []
    assert "resume_window" not in calls

@pytest.mark.asyncio
async def test_terminal_select_window_does_not_recreate_missing_tmux_window_by_default() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    runtime = FakeRuntime(window_exists=False)

    with pytest.raises(RuntimeError, match="missing tmux window"):
        await handle_message_for_test(
            FakeWriter(),
            FakeBulkWriter(),
            object(),
            runtime,
            terminal,
            supervisor,
            FakeAgentToolWatcher(calls),
            {},
            {},
            AgentMessage(
                type="terminal_select_window",
                client_id=UUID("12345678-1234-5678-1234-567812345678"),
                window_id=WINDOW_ID,
                request_id="request-1",
                payload={
                    "remote_session_id": "pool",
                    "remote_window_id": "@7",
                    "view_id": str(VIEW_ID),
                    "cwd": "/workspace/project",
                    "shell_command": "codex",
                },
            ),
        )

    assert runtime.recreated == []
    assert supervisor.resume_calls == []
    assert "resume_window" not in calls

@pytest.mark.asyncio
async def test_terminal_attach_passive_tmux_selection_does_not_resume_other_window() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    writer = FakeWriter()
    runtime = FakeRuntime(pane_current_command="bash")
    other_window_id = UUID("11111111-2222-3333-4444-555555555555")
    captured_selection_sender = None

    async def attach_with_selection(_window_id, _sender, *, selection_sender=None, view_id=None):
        nonlocal captured_selection_sender
        calls.append("attach_with_selection")
        captured_selection_sender = selection_sender

    terminal.attach_with_selection = attach_with_selection
    terminal.register_window(other_window_id, "pool", "@8")

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
            },
        ),
    )

    assert captured_selection_sender is not None
    await captured_selection_sender(other_window_id)

    assert supervisor.resume_calls == []
    assert "resume_window" not in calls
    assert writer.messages[-1].type == "terminal_selection"
    assert writer.messages[-1].window_id == other_window_id

@pytest.mark.asyncio
async def test_terminal_attach_can_explicitly_recreate_with_default_shell_when_resume_is_available() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=False)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreate_shell_commands == [None]
    assert supervisor.resume_calls == [(WINDOW_ID, True)]
    assert writer.messages[-1].payload["shell_command"] == "codex"

@pytest.mark.asyncio
async def test_terminal_attach_does_not_resume_when_recreate_finds_existing_local_window() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=False, recreation_created=False)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreated == [WINDOW_ID]
    assert runtime.recreate_shell_commands == [None]
    assert supervisor.resume_calls == []
    assert "resume_window" not in calls
    assert writer.messages[-1].payload["remote_window_id"] == "@9"

@pytest.mark.asyncio
async def test_terminal_attach_marks_cleanup_activity_for_terminal_viewed() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=True, window_activity_timestamp=800.0)

    class Cleanup:
        def __init__(self) -> None:
            self.registered: list[tuple[UUID, ClientRuntimeWindow]] = []
            self.touched: list[UUID] = []
            self.attached: list[UUID] = []

        def register_window(self, window_id: UUID, runtime_window: ClientRuntimeWindow) -> None:
            self.registered.append((window_id, runtime_window))

        def touch_window(self, window_id: UUID) -> None:
            self.touched.append(window_id)

        def attach_view(self, window_id: UUID) -> None:
            self.attached.append(window_id)

    cleanup = Cleanup()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "activity": "terminal_viewed",
            },
        ),
        stale_window_cleanup=cleanup,
    )

    assert runtime.killed == []
    assert runtime.recreated == []
    assert cleanup.touched == [WINDOW_ID]
    assert cleanup.attached == [WINDOW_ID]
    assert cleanup.registered[0][0] == WINDOW_ID
    assert writer.messages[-1].payload["remote_window_id"] == "@7"

@pytest.mark.asyncio
async def test_terminal_attach_without_viewed_activity_only_protects_current_view() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=True, window_activity_timestamp=800.0)

    class Cleanup:
        def __init__(self) -> None:
            self.touched: list[UUID] = []
            self.attached: list[UUID] = []

        def register_window(self, _window_id: UUID, _runtime_window: ClientRuntimeWindow) -> None:
            return None

        def touch_window(self, window_id: UUID) -> None:
            self.touched.append(window_id)

        def attach_view(self, window_id: UUID) -> None:
            self.attached.append(window_id)

    cleanup = Cleanup()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
            },
        ),
        stale_window_cleanup=cleanup,
    )

    assert cleanup.touched == []
    assert cleanup.attached == [WINDOW_ID]
    assert runtime.killed == []
    assert runtime.recreated == []
    assert writer.messages[-1].payload["remote_window_id"] == "@7"

@pytest.mark.asyncio
async def test_repeated_terminal_attach_for_same_view_does_not_duplicate_cleanup_attach() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    writer = FakeWriter()

    class Cleanup:
        def __init__(self) -> None:
            self.attached: list[UUID] = []

        def register_window(self, _window_id: UUID, _runtime_window: ClientRuntimeWindow) -> None:
            return None

        def touch_window(self, _window_id: UUID) -> None:
            return None

        def attach_view(self, window_id: UUID) -> None:
            self.attached.append(window_id)

    cleanup = Cleanup()
    terminal_view_window_ids = {}
    message = AgentMessage(
        type="terminal_attach",
        client_id=UUID("12345678-1234-5678-1234-567812345678"),
        window_id=WINDOW_ID,
        request_id="request-1",
        payload={
            "remote_session_id": "pool",
            "remote_window_id": "@7",
            "view_id": str(VIEW_ID),
            "activity": "terminal_viewed",
        },
    )

    for _ in range(2):
        await handle_message_for_test(
            writer,
            FakeBulkWriter(),
            object(),
            FakeRuntime(window_exists=True),
            terminal,
            supervisor,
            FakeAgentToolWatcher(calls),
            {},
            terminal_view_window_ids,
            message,
            stale_window_cleanup=cleanup,
        )

    assert cleanup.attached == [WINDOW_ID]
