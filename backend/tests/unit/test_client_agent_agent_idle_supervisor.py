from tests.unit.test_client_agent_agent_idle_support import *

def test_session_id_from_payload_extracts_provider_session_ids(tmp_path: Path) -> None:
    cursor_store = tmp_path / "chats" / "team" / "cursor-session" / "store.db"
    cursor_store.parent.mkdir(parents=True)
    write_cursor_store(cursor_store, agent_id="cursor-session")

    assert session_id_from_payload("claude_code", {"sessionId": "claude-session"}, None) == "claude-session"
    assert (
        session_id_from_payload(
            "codex",
            {"type": "session_meta", "payload": {"id": "codex-session"}},
            None,
        )
        == "codex-session"
    )
    assert session_id_from_payload("cursor_cli", {}, str(cursor_store)) == "cursor-session"

def test_session_ref_from_event_ignores_claude_local_command_meta() -> None:
    event = ManagedAiEvent(
        provider="claude_code",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        source_path="/tmp/claude-session.jsonl",
        offset=42,
        cursor=42,
        project_path="/workspace/project",
        payload={
            "type": "user",
            "sessionId": "claude-session",
            "isMeta": True,
            "message": {
                "role": "user",
                "content": "<bash-input>env | grep claude</bash-input>",
            },
        },
    )

    assert session_ref_from_event(event) is None

def test_latest_session_refs_read_managed_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    claude_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "project"
        / "claude.jsonl"
    )
    claude_file.parent.mkdir(parents=True)
    claude_file.write_text(
        json.dumps({"sessionId": "claude-session", "type": "assistant"}) + "\n",
        encoding="utf-8",
    )

    codex_file = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(WINDOW_ID)
        / "sessions"
        / "2026"
        / "05"
        / "26"
        / "rollout-2026-05-26T00-00-00-codex-session.jsonl"
    )
    codex_file.parent.mkdir(parents=True)
    codex_file.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "codex-session"}}) + "\n",
        encoding="utf-8",
    )

    cursor_store = (
        home
        / ".web-terminal-acp"
        / "cursor-homes"
        / str(WINDOW_ID)
        / "chats"
        / "team"
        / "cursor-session"
        / "store.db"
    )
    cursor_store.parent.mkdir(parents=True)
    write_cursor_store(cursor_store, agent_id="cursor-session")

    assert latest_claude_session_ref(WINDOW_ID).session_id == "claude-session"
    assert latest_codex_session_ref(WINDOW_ID).session_id == "codex-session"
    assert latest_cursor_session_ref(WINDOW_ID).session_id == "cursor-session"

def test_latest_resume_command_uses_original_project_for_claude_worktree_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    claude_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "-workspace-project"
        / "claude-session.jsonl"
    )
    claude_file.parent.mkdir(parents=True)
    claude_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "attachment",
                        "cwd": "/workspace/project",
                        "sessionId": "claude-session",
                    }
                ),
                json.dumps(
                    {
                        "type": "worktree-state",
                        "sessionId": "claude-session",
                        "worktreeSession": {
                            "originalCwd": "/workspace/project",
                            "worktreeName": "feature-blog",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "cwd": "/workspace/project/.claude/worktrees/feature-blog",
                        "sessionId": "claude-session",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert latest_claude_session_ref(WINDOW_ID).claude_worktree_name == "feature-blog"
    assert (
        latest_resume_command(WINDOW_ID, project_path="/workspace/project")
        == "cd /workspace/project && WEB_TERMINAL_AUTO_RESUME=1 claude --dangerously-skip-permissions --resume claude-session"
    )

def test_latest_resume_command_uses_newest_managed_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    old_claude_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "project"
        / "claude.jsonl"
    )
    old_claude_file.parent.mkdir(parents=True)
    old_claude_file.write_text(
        json.dumps({"sessionId": "claude-session"}) + "\n",
        encoding="utf-8",
    )
    os.utime(old_claude_file, (1000, 1000))

    new_codex_file = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(WINDOW_ID)
        / "sessions"
        / "2026"
        / "05"
        / "26"
        / "rollout-2026-05-26T00-00-00-codex-session.jsonl"
    )
    new_codex_file.parent.mkdir(parents=True)
    new_codex_file.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "codex-session"}}) + "\n",
        encoding="utf-8",
    )
    os.utime(new_codex_file, (2000, 2000))

    assert (
        latest_resume_command(WINDOW_ID, project_path="/workspace/project")
        == "cd /workspace/project && WEB_TERMINAL_AUTO_RESUME=1 codex --dangerously-bypass-approvals-and-sandbox resume codex-session"
    )

@pytest.mark.asyncio
async def test_resume_window_only_uses_latest_session_when_explicitly_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    codex_file = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(WINDOW_ID)
        / "sessions"
        / "2026"
        / "05"
        / "26"
        / "rollout-2026-05-26T00-00-00-codex-session.jsonl"
    )
    codex_file.parent.mkdir(parents=True)
    codex_file.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "codex-session"}}) + "\n",
        encoding="utf-8",
    )
    runtime = FakeRuntime()
    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=runtime,
        suspension_dir=tmp_path,
    )
    supervisor.register_window(WINDOW_ID, "/workspace/project")

    await supervisor.resume_window(WINDOW_ID)

    assert runtime.calls == []

    await supervisor.resume_window(WINDOW_ID, allow_latest_session=True)

    assert runtime.calls == [
        [
            "tmux",
            "send-keys",
            "-t",
            "pool:@7",
            "--",
            "cd /workspace/project && WEB_TERMINAL_AUTO_RESUME=1 codex --dangerously-bypass-approvals-and-sandbox resume codex-session",
            "C-m",
        ]
    ]

@pytest.mark.asyncio
async def test_idle_supervisor_suspends_after_one_hour(tmp_path: Path) -> None:
    now = 10_000.0
    terminated: list[tuple[AgentProcess, ...]] = []
    process = AgentProcess(
        provider="codex",
        pid=123,
        cmdline="codex",
        command_name="codex",
        cwd="/workspace/project",
    )

    async def detector(window_id, terminal, runtime):
        return {"codex": (process,)}

    async def terminator(processes):
        terminated.append(processes)

    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=FakeRuntime(),
        idle_seconds=3600,
        suspension_dir=tmp_path,
        clock=lambda: now,
        process_detector=detector,
        process_terminator=terminator,
    )
    await supervisor.observe_events(
        [
            ManagedAiEvent(
                provider="codex",
                client_id=CLIENT_ID,
                window_id=WINDOW_ID,
                source_path=None,
                offset=0,
                cursor=0,
                project_path="/workspace/project",
                payload={
                    "trace_id": "codex-session",
                    "client_id": str(CLIENT_ID),
                    "virtual_window_id": str(WINDOW_ID),
                },
            )
        ]
    )
    supervisor._states[(WINDOW_ID, "codex")].last_output_at = now - 3601

    await supervisor.maybe_suspend_window(WINDOW_ID)

    assert terminated == [(process,)]
    payload = json.loads((tmp_path / f"{WINDOW_ID}.json").read_text(encoding="utf-8"))
    assert payload["agents"][0]["session_id"] == "codex-session"
    assert payload["agents"][0]["cwd"] == "/workspace/project"

@pytest.mark.asyncio
async def test_idle_supervisor_preserves_claude_worktree_metadata_until_suspend(
    tmp_path: Path,
) -> None:
    now = 10_000.0
    terminated: list[tuple[AgentProcess, ...]] = []
    process = AgentProcess(
        provider="claude_code",
        pid=123,
        cmdline="claude",
        command_name="claude",
        cwd="/workspace/project/.claude/worktrees/feature-blog",
    )

    async def detector(window_id, terminal, runtime):
        return {"claude_code": (process,)}

    async def terminator(processes):
        terminated.append(processes)

    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=FakeRuntime(),
        idle_seconds=3600,
        suspension_dir=tmp_path,
        clock=lambda: now,
        process_detector=detector,
        process_terminator=terminator,
    )
    await supervisor.observe_events(
        [
            ManagedAiEvent(
                provider="claude_code",
                client_id=CLIENT_ID,
                window_id=WINDOW_ID,
                source_path=None,
                offset=0,
                cursor=0,
                project_path="/workspace/project",
                payload={
                    "type": "worktree-state",
                    "sessionId": "claude-session",
                    "worktreeSession": {
                        "originalCwd": "/workspace/project",
                        "worktreeName": "feature-blog",
                    },
                },
            ),
            ManagedAiEvent(
                provider="claude_code",
                client_id=CLIENT_ID,
                window_id=WINDOW_ID,
                source_path=None,
                offset=1,
                cursor=1,
                project_path="/workspace/project",
                payload={"type": "assistant", "sessionId": "claude-session"},
            ),
        ]
    )
    supervisor._states[(WINDOW_ID, "claude_code")].last_output_at = now - 3601

    await supervisor.maybe_suspend_window(WINDOW_ID)

    assert terminated == [(process,)]
    payload = json.loads((tmp_path / f"{WINDOW_ID}.json").read_text(encoding="utf-8"))
    assert payload["agents"][0]["claude_worktree_name"] == "feature-blog"
    assert payload["agents"][0]["claude_worktree_original_cwd"] == "/workspace/project"

@pytest.mark.asyncio
async def test_idle_supervisor_does_not_suspend_attached_window(tmp_path: Path) -> None:
    terminated: list[tuple[AgentProcess, ...]] = []

    async def detector(window_id, terminal, runtime):
        return {
            "codex": (
                AgentProcess(
                    provider="codex",
                    pid=123,
                    cmdline="codex",
                    command_name="codex",
                    cwd="/workspace/project",
                ),
            )
        }

    async def terminator(processes):
        terminated.append(processes)

    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=FakeRuntime(),
        idle_seconds=3600,
        suspension_dir=tmp_path,
        clock=lambda: 10_000.0,
        process_detector=detector,
        process_terminator=terminator,
    )
    supervisor.attach_view(UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"), WINDOW_ID)

    await supervisor.maybe_suspend_window(WINDOW_ID)

    assert terminated == []
