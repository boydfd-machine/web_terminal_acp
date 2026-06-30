from tests.unit.test_client_agent_runner_support import *

def test_should_restore_agent_tool_watcher_requires_managed_marker() -> None:
    assert _should_restore_agent_tool_watcher(
        ClientRuntimeWindow(
            remote_session_id="client_pool",
            remote_window_id="@1",
            local_window_id=WINDOW_ID,
            managed_agent_tools=True,
        )
    )

    assert not _should_restore_agent_tool_watcher(
        ClientRuntimeWindow(
            remote_session_id="client_pool",
            remote_window_id="@2",
            local_window_id=WINDOW_ID,
            managed_agent_tools=False,
        )
    )
    assert not _should_restore_agent_tool_watcher(
        ClientRuntimeWindow(
            remote_session_id="client_pool",
            remote_window_id="@3",
            managed_agent_tools=True,
        )
    )

@pytest.mark.asyncio
async def test_aux_terminal_attach_sends_aux_output_message() -> None:
    writer = FakeWriter()
    bulk_writer = FakeBulkWriter()
    aux_terminal = FakeAuxTerminal()

    await _handle_agent_message(
        writer,
        bulk_writer,
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        aux_terminal,
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="aux_terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-aux",
            payload={
                "aux_terminal_id": "aux-1",
                "view_id": str(VIEW_ID),
            },
        ),
    )

    senders = [call for call in aux_terminal.calls if call[0] == "attach"]
    assert senders == [("attach", "aux-1")]
    attach_sender = aux_terminal.attach_sender
    await attach_sender(b"aux output\n")

    assert writer.messages[-1].type == "aux_terminal_attach_result"
    assert bulk_writer.terminal_messages[-1].type == "aux_terminal_output"
    assert bulk_writer.terminal_messages[-1].payload["view_id"] == str(VIEW_ID)

@pytest.mark.asyncio
async def test_aux_terminal_kill_removes_aux_target() -> None:
    aux_terminal = FakeAuxTerminal()

    await _handle_agent_message(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        aux_terminal,
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="aux_terminal_kill",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            payload={"aux_terminal_id": "aux-1"},
        ),
    )

    assert aux_terminal.calls == [("kill", "aux-1")]

@pytest.mark.asyncio
async def test_run_client_agent_uses_capped_reconnect_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    attempts = 0
    sleeps: list[float] = []

    async def fake_run_once(config: ClientAgentConfig) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts <= 7:
            raise OSError("network unavailable")
        return True

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(client_agent_runner, "_run_client_agent_once", fake_run_once)
    monkeypatch.setattr(client_agent_runner, "_reconnect_sleep_seconds", lambda delay: delay)
    monkeypatch.setattr(client_agent_runner.asyncio, "sleep", fake_sleep)

    config = ClientAgentConfig(
        client_id=client_id,
        token="secret-token",
        server_url="http://control.example.com",
        name="edge-client",
        install_path=Path("/opt/web-terminal-acp-client"),
    )

    await client_agent_runner.run_client_agent(config)

    assert sleeps == [1, 2, 4, 8, 16, 30, 30]
@pytest.mark.asyncio
async def test_run_cleanup_step_times_out_hanging_awaitable() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")

    async def hangs() -> None:
        await asyncio.Event().wait()

    await asyncio.wait_for(
        _run_cleanup_step(
            "hanging",
            hangs(),
            client_id=client_id,
            timeout_seconds=0.01,
        ),
        timeout=0.1,
    )

@pytest.mark.asyncio
async def test_run_cleanup_step_suppresses_child_task_cancellation() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    task = asyncio.create_task(asyncio.sleep(10))
    task.cancel()

    await _run_cleanup_step(
        "cancelled_child",
        task,
        client_id=client_id,
        timeout_seconds=0.1,
    )

@pytest.mark.asyncio
async def test_terminal_attach_resumes_suspended_agent_before_attach() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
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
            },
        ),
    )

    assert calls[:4] == [
        "attach_view",
        "register_window",
        "register_window_supervisor",
        "resume_window",
    ]
    assert calls[4] == "attach_with_selection"
    assert supervisor.resume_calls == [(WINDOW_ID, False)]
    assert writer.messages[-1].type == "terminal_attach_result"

@pytest.mark.asyncio
async def test_terminal_select_window_resumes_suspended_agent_before_select() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
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
            },
        ),
    )

    assert calls == [
        "register_window",
        "register_window_supervisor",
        "attach_view",
        "resume_window",
        "select_window",
    ]
    assert supervisor.resume_calls == [(WINDOW_ID, False)]
    assert writer.messages[-1].type == "terminal_attach_result"


@pytest.mark.asyncio
async def test_process_liveness_message_returns_active_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = FakeWriter()
    runtime = FakeRuntime()
    active_processes = ["sleep 120"]

    async def fake_active_processes(_runtime, *, remote_session_id, remote_window_id):
        assert remote_session_id == "pool"
        assert remote_window_id == "@9"
        return active_processes

    monkeypatch.setattr(client_agent_runner, "active_non_shell_processes_for_runtime_window", fake_active_processes)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="process_liveness",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="process-check-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@9",
            },
        ),
    )

    assert writer.messages[-1] == AgentMessage(
        type="process_liveness_result",
        client_id=UUID("12345678-1234-5678-1234-567812345678"),
        window_id=WINDOW_ID,
        request_id="process-check-1",
        payload={"active_processes": active_processes},
    )


@pytest.mark.asyncio
async def test_terminal_attach_skips_resume_when_recreate_reuses_active_agent_session() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(
        window_exists=False,
        recreation_created=False,
        pane_current_command="codex",
    )

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
    assert supervisor.resume_calls == []
    assert "resume_window" not in calls
    assert calls[-1] == "attach_with_selection"
    assert writer.messages[-1].payload["remote_window_id"] == "@9"

@pytest.mark.asyncio
async def test_create_window_registers_existing_unified_agent_tool_watcher() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    watcher = FakeAgentToolWatcher(calls)
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        terminal,
        supervisor,
        watcher,
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={"cwd": "/workspace/project"},
        ),
    )

    assert calls == [
        "create_window",
        "register_window",
        "register_window_supervisor",
        "watch_window",
    ]
    assert watcher.watched == [(WINDOW_ID, "/workspace/project")]
    assert writer.messages[-1].type == "create_window_result"

@pytest.mark.asyncio
async def test_create_window_scopes_agent_tool_watcher_to_detected_provider() -> None:
    watcher = FakeAgentToolWatcher([])

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime([]),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        watcher,
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={"cwd": "/workspace/project", "shell_command": "env FOO=1 cursor-agent"},
        ),
    )

    assert watcher.watched == [(WINDOW_ID, "/workspace/project", frozenset({"cursor_cli"}))]

@pytest.mark.asyncio
async def test_create_window_can_run_in_background_without_blocking_control_messages() -> None:
    create_started = asyncio.Event()
    create_continue = asyncio.Event()
    calls: list[str] = []
    writer = FakeWriter()
    runtime = BlockingCreateRuntime(calls, create_started, create_continue)

    await _handle_agent_message(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        FakeAuxTerminal(),
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="create-1",
            payload={"cwd": "/workspace/project"},
        ),
        create_window_tasks=set(),
    )
    await asyncio.wait_for(create_started.wait(), timeout=1.0)

    await _handle_agent_message(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        FakeAuxTerminal(),
        {},
        set(),
        asyncio.Semaphore(1),
        {},
        AgentMessage(
            type="agent_config_get",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="config-1",
            payload={"agent": "codex"},
        ),
        create_window_tasks=set(),
    )

    assert writer.messages[-1].type == "agent_config_result"
    assert calls == ["create_window"]

    create_continue.set()
    for _ in range(20):
        if any(message.type == "create_window_result" for message in writer.messages):
            break
        await asyncio.sleep(0.01)
    assert [message.type for message in writer.messages] == [
        "agent_config_result",
        "create_window_result",
    ]

@pytest.mark.asyncio
async def test_terminal_attach_reuses_registered_recreated_window_for_stale_request() -> None:
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    terminal.registered_remote_windows[str(WINDOW_ID)] = ("pool", "@9")
    runtime = FakeRuntime(calls, window_exists=True)
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_attach",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="attach-stale",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "/bin/bash",
            },
        ),
    )

    assert runtime.has_window_calls == [("@9", "pool")]
    assert runtime.recreated == []
    assert "unregister_window" not in calls
    assert writer.messages[-1].type == "terminal_attach_result"
    assert writer.messages[-1].payload["remote_window_id"] == "@9"

@pytest.mark.asyncio
async def test_terminal_capture_returns_current_terminal_output() -> None:
    calls: list[str] = []
    writer = FakeWriter()
    terminal = FakeTerminal(calls)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        terminal,
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_capture",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="capture-1",
            payload={},
        ),
    )

    assert writer.messages[-1].type == "terminal_capture_result"
    assert writer.messages[-1].request_id == "capture-1"
    assert writer.messages[-1].payload["window_id"] == str(WINDOW_ID)
    assert calls == ["capture_output_bytes"]
    assert terminal.capture_kwargs == [{"view_id": None, "history_lines": None}]
