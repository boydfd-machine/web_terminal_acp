from tests.unit.test_client_agent_agent_tool_watchers_support import *


def test_agent_tool_collectors_are_centralized_by_provider() -> None:
    assert AGENT_TOOL_COLLECTORS == (
        ("codex", "collect_codex_watch_events"),
        ("claude_code", "collect_claude_code_watch_events"),
        ("cursor_cli", "collect_cursor_watch_events"),
        ("antigravity_cli", "collect_antigravity_watch_events"),
    )


def test_collect_all_events_can_filter_to_declared_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def collect(state, *, client_id, window_id, project_path):
        called.append("cursor_cli")
        return []

    monkeypatch.setattr("app.client_agent.agent_tool_watchers.collect_cursor_watch_events", collect)

    _collect_all_events(
        AgentToolWatcherState(),
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
        providers=frozenset({"cursor_cli"}),
    )

    assert called == ["cursor_cli"]


def test_collect_codex_watch_events_preserves_payload_shape_and_project_attribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    session_file.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "done"}],
                },
                "timestamp": "2026-05-23T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [session_file],
    )
    state = AgentToolWatcherState()

    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(events) == 1
    event = events[0]
    assert event.provider == "codex"
    assert event.source_path == str(session_file)
    assert event.offset == 0
    assert event.cursor == 0
    assert event.project_path == "/workspace/project"
    assert event.payload["client_id"] == str(CLIENT_ID)
    assert event.payload["virtual_window_id"] == str(WINDOW_ID)
    assert event.payload["project_path"] == "/workspace/project"
    assert state.codex_offsets[session_file] == session_file.stat().st_size


def test_initialize_agent_tool_watcher_state_starts_stale_jsonl_collectors_at_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    codex_session = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    codex_session.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "old codex"}],
                },
                "timestamp": "2026-05-23T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    claude_session = tmp_path / "claude-session.jsonl"
    claude_session.write_text(
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "old claude"}})
        + "\n",
        encoding="utf-8",
    )
    now = 1_780_000_000.0
    old = now - watchers.CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS - 1
    os.utime(codex_session, (old, old))
    os.utime(claude_session, (old, old))
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [codex_session],
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_claude_code_jsonl_files",
        lambda window_id: [claude_session],
    )
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)

    assert (
        collect_codex_watch_events(
            state,
            client_id=CLIENT_ID,
            window_id=WINDOW_ID,
            project_path="/workspace/project",
        )
        == []
    )
    assert (
        collect_claude_code_watch_events(
            state,
            client_id=CLIENT_ID,
            window_id=WINDOW_ID,
            project_path="/workspace/project",
        )
        == []
    )

    codex_new_offset = codex_session.stat().st_size
    codex_session.write_text(
        codex_session.read_text(encoding="utf-8")
        + json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "new codex"}],
                },
                "timestamp": "2026-05-23T00:00:01Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    claude_new_offset = claude_session.stat().st_size
    claude_session.write_text(
        claude_session.read_text(encoding="utf-8")
        + json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "content": "new claude"}}
        )
        + "\n",
        encoding="utf-8",
    )

    codex_events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    claude_events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.offset for event in codex_events] == [codex_new_offset]
    assert codex_events[0].payload["payload"]["content"][0]["text"] == "new codex"
    assert [event.offset for event in claude_events] == [claude_new_offset]
    assert claude_events[0].payload["message"]["content"] == "new claude"


def test_initialize_agent_tool_watcher_state_bootstraps_latest_recent_claude_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_session = tmp_path / "old-claude-session.jsonl"
    active_session = tmp_path / "active-claude-session.jsonl"
    stale_session.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "old-claude-session",
                "message": {"role": "assistant", "content": "old claude"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    active_session.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "active-claude-session",
                "message": {"role": "assistant", "content": "bootstrap claude"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    now = 1_780_000_000.0
    old = now - watchers.CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS - 1
    os.utime(stale_session, (old, old))
    os.utime(active_session, (now - 1, now - 1))
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_claude_code_jsonl_files",
        lambda window_id: [stale_session, active_session],
    )
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)
    events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.offset for event in events] == [0]
    assert events[0].source_path == str(active_session)
    assert events[0].payload["message"]["content"] == "bootstrap claude"
    assert state.claude_code_offsets[stale_session] == stale_session.stat().st_size


def test_initialize_agent_tool_watcher_state_bootstraps_latest_recent_codex_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_session = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    active_session = tmp_path / "rollout-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    stale_session.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "old skipped"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    active_session.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "bootstrap me"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    now = 1_780_000_000.0
    old = now - watchers.CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS - 1
    os.utime(stale_session, (old, old))
    os.utime(active_session, (now - 1, now - 1))
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [stale_session, active_session],
    )
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)
    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.offset for event in events] == [0]
    assert events[0].source_path == str(active_session)
    assert events[0].payload["payload"]["content"][0]["text"] == "bootstrap me"
    assert state.codex_offsets[stale_session] == stale_session.stat().st_size


def test_initialize_agent_tool_watcher_state_does_not_bootstrap_cloned_codex_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    codex_home = home / ".web-terminal-acp" / "codex-homes" / str(WINDOW_ID)
    session_file = (
        codex_home
        / "sessions"
        / "2026"
        / "06"
        / "09"
        / "rollout-2026-06-09T00-00-00-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    )
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "copied history"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (codex_home / watchers.CODEX_CLONE_MARKER).write_text("{}", encoding="utf-8")
    now = 1_780_000_000.0
    os.utime(session_file, (now - 1, now - 1))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)
    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert events == []
    assert state.codex_offsets[session_file] == session_file.stat().st_size


def test_initialize_agent_tool_watcher_state_resumes_stale_codex_session_at_complete_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    first_line = json.dumps(
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "complete"}],
            },
        }
    )
    session_file.write_text(first_line + "\n" + '{"type":"response_item"', encoding="utf-8")
    now = 1_780_000_000.0
    old = now - watchers.CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS - 1
    os.utime(session_file, (old, old))
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [session_file],
    )
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)

    assert state.codex_offsets[session_file] == len((first_line + "\n").encode("utf-8"))


def test_collect_codex_watch_events_resets_offset_after_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "rollout-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    session_file.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "after rotate"}],
                },
                "timestamp": "2026-05-23T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [session_file],
    )
    state = AgentToolWatcherState(codex_offsets={session_file: 10_000})

    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(events) == 1
    assert events[0].offset == 0
    assert events[0].cursor == 0
    assert events[0].payload["payload"]["content"][0]["text"] == "after rotate"
    assert state.codex_offsets[session_file] == session_file.stat().st_size


def test_collect_codex_watch_events_hardlinks_session_to_global_resume_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_file = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(WINDOW_ID)
        / "sessions"
        / "2026"
        / "06"
        / "01"
        / "rollout-2026-06-01T00-00-00-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    )
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "global codex"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    global_session_file = (
        home
        / ".codex"
        / "sessions"
        / "2026"
        / "06"
        / "01"
        / "rollout-2026-06-01T00-00-00-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    )
    assert len(events) == 1
    assert global_session_file.samefile(session_file)


def test_collect_claude_code_watch_events_reads_managed_home_and_tracks_offsets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "managed" / "nested" / "session.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "claude-session-1",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_claude_code_jsonl_files",
        lambda window_id: [session_file],
    )
    state = AgentToolWatcherState()

    first = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    second = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(first) == 1
    event = first[0]
    assert event.provider == "claude_code"
    assert event.source_path == str(session_file)
    assert event.offset == 0
    assert event.cursor == 0
    assert event.project_path == "/workspace/project"
    assert event.payload["WEB_TERMINAL_CLIENT_ID"] == str(CLIENT_ID)
    assert event.payload["WEB_TERMINAL_WINDOW_ID"] == str(WINDOW_ID)
    assert event.payload["WEB_TERMINAL_PROJECT_PATH"] == "/workspace/project"
    assert event.payload["type"] == "assistant"
    assert second == []
    assert state.claude_code_offsets[session_file] == session_file.stat().st_size
