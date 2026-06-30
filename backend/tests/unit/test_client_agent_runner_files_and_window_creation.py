from tests.unit.test_client_agent_runner_support import *

@pytest.mark.asyncio
async def test_terminal_capture_passes_history_lines_to_terminal() -> None:
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
            request_id="capture-history",
            payload={"history_lines": "5000"},
        ),
    )

    assert writer.messages[-1].type == "terminal_capture_result"
    assert writer.messages[-1].request_id == "capture-history"
    assert terminal.capture_kwargs == [{"view_id": None, "history_lines": 5000}]

@pytest.mark.asyncio
async def test_file_read_returns_requested_file_bytes(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text('{"task":"demo"}', encoding="utf-8")
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="file_read",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="file-read-1",
            payload={"path": str(artifact_path), "max_bytes": 4096},
        ),
    )

    assert writer.messages[-1].type == "file_read_result"
    assert writer.messages[-1].request_id == "file-read-1"
    assert writer.messages[-1].payload["window_id"] == "12345678-1234-5678-1234-567812345678"
    assert writer.messages[-1].payload["data"] == "eyJ0YXNrIjoiZGVtbyJ9"

@pytest.mark.asyncio
async def test_file_list_returns_direct_entries(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="file_list",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="file-list-1",
            payload={"path": str(tmp_path)},
        ),
    )

    assert writer.messages[-1].type == "file_list_result"
    assert writer.messages[-1].request_id == "file-list-1"
    assert [(entry["name"], entry["kind"]) for entry in writer.messages[-1].payload["entries"]] == [
        ("docs", "directory"),
        ("README.md", "file"),
    ]

@pytest.mark.asyncio
async def test_file_write_writes_requested_bytes(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "upload.txt"
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="file_write",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="file-write-1",
            payload={
                **TerminalPayload.from_bytes(WINDOW_ID, b"uploaded").model_dump(mode="json"),
                "path": str(target),
            },
        ),
    )

    assert writer.messages[-1].type == "file_write_result"
    assert writer.messages[-1].request_id == "file-write-1"
    assert target.read_text(encoding="utf-8") == "uploaded"

@pytest.mark.asyncio
async def test_terminal_input_direct_sends_to_base_terminal() -> None:
    calls: list[str] = []

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_input_direct",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            payload={
                "window_id": str(WINDOW_ID),
                "data": "cHJvbXB0Cg==",
                "remote_session_id": "pool",
                "remote_window_id": "@7",
            },
        ),
    )

    assert calls == ["send_input_direct"]

@pytest.mark.asyncio
async def test_create_window_applies_agent_config_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    applied: list[tuple[str, str, bool]] = []
    restored: list[object] = []

    def fake_apply(selection, *, window_id, home=None, protect_system_config_skills=False):
        applied.append((selection.agent, window_id, protect_system_config_skills))
        calls.append("apply_config")
        return AgentConfig(agent=selection.agent, sections=[])

    def fake_restore(payload, *, home=None):
        restored.append(payload)
        calls.append("restore_system_config")

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.apply_agent_config_selection",
        fake_apply,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.restore_system_agent_config_files_payload",
        fake_restore,
    )

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "agent_config_selection": {
                    "agent": "codex",
                    "sections": [
                        {"id": "skills", "items": [{"id": "docker", "enabled": False}]}
                    ],
                },
                "system_config_files": {
                    "version": 1,
                    "files": [
                        {
                            "path": "skills/image-to-ppt/SKILL.md",
                            "content_b64": "LS0tCm5hbWU6IEltYWdlIHRvIFBQVGotLS0K",
                        }
                    ],
                },
            },
        ),
    )

    assert calls[:3] == ["restore_system_config", "apply_config", "create_window"]
    assert restored == [
        {
            "version": 1,
            "files": [
                {
                    "path": "skills/image-to-ppt/SKILL.md",
                    "content_b64": "LS0tCm5hbWU6IEltYWdlIHRvIFBQVGotLS0K",
                }
            ],
        }
    ]
    assert applied == [("codex", str(WINDOW_ID), False)]


@pytest.mark.asyncio
async def test_create_window_does_not_install_builtin_mcp_before_runtime_create() -> None:
    calls: list[str] = []
    installed: list[dict[str, str | None]] = []

    def fake_install(**kwargs):
        calls.append("install_builtin_mcp")
        installed.append(kwargs)

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
            },
        ),
        install_builtin_mcp=fake_install,
    )

    assert calls[:1] == ["create_window"]
    assert installed == []


@pytest.mark.asyncio
async def test_create_window_materializes_agent_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    materialized: list[tuple[str, str, str]] = []

    def fake_materialize(profile_id, agent, *, window_id, home=None):
        materialized.append((profile_id, agent, window_id))
        calls.append("materialize_profile")
        return AgentConfig(agent="codex", sections=[])

    monkeypatch.setattr(
        "app.client_agent.runner.agent_profile_service.materialize_agent_profile_for_window",
        fake_materialize,
    )

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "agent_profile_id": "builder",
                "agent_profile_agent": "codex",
            },
        ),
    )

    assert calls[:2] == ["materialize_profile", "create_window"]
    assert materialized == [("builder", "codex", str(WINDOW_ID))]

@pytest.mark.asyncio
async def test_create_window_clones_agent_homes_before_runtime_create(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    cloned: list[tuple[str, UUID, str | None, bool]] = []

    def fake_clone(source_window_id, target_window_id, *, source_cwd=None, isolate_sessions=False):
        cloned.append((source_window_id, target_window_id, source_cwd, isolate_sessions))
        calls.append("clone_homes")
        return type(
            "CloneResult",
            (),
            {
                "resume_commands": {"codex": "codex resume cloned-session"},
            },
        )()

    monkeypatch.setattr(
        "app.client_agent.runner.clone_window_agent_homes",
        fake_clone,
    )

    runtime = FakeRuntime(calls)

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        runtime,
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "clone_source_window_id": "source-window-1",
            },
        ),
    )

    assert calls[:2] == ["clone_homes", "create_window"]
    assert cloned == [("source-window-1", WINDOW_ID, "/workspace/project", False)]
    assert runtime.create_shell_commands == ["codex resume cloned-session"]

@pytest.mark.asyncio
async def test_create_window_passes_artifact_clone_session_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloned: list[bool] = []

    def fake_clone(source_window_id, target_window_id, *, source_cwd=None, isolate_sessions=False):
        cloned.append(isolate_sessions)
        return type(
            "CloneResult",
            (),
            {
                "resume_commands": {"codex": "codex resume isolated-session"},
            },
        )()

    monkeypatch.setattr(
        "app.client_agent.runner.clone_window_agent_homes",
        fake_clone,
    )

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "clone_source_window_id": "source-window-1",
                "isolate_clone_sessions": True,
            },
        ),
    )

    assert cloned == [True]

@pytest.mark.asyncio
async def test_kill_window_removes_window_from_unified_agent_tool_watcher_first() -> None:
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
            type="kill_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={},
        ),
    )

    assert calls == ["unwatch_window", "remove_window_supervisor", "remove_window", "kill_window"]
    assert watcher.removed == [WINDOW_ID]
    assert writer.messages[-1].type == "kill_window_result"

@pytest.mark.asyncio
async def test_terminal_attach_can_explicitly_recreate_missing_tmux_window_before_resume() -> None:
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
                "shell_command": "/bin/bash",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreated == [WINDOW_ID]
    assert calls[:5] == [
        "attach_view",
        "unregister_window",
        "register_window",
        "register_window_supervisor",
        "resume_window",
    ]
    assert calls[5] == "attach_with_selection"
    assert supervisor.resume_calls == [(WINDOW_ID, True)]
    assert writer.messages[-1].payload["remote_window_id"] == "@9"
