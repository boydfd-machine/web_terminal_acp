from tests.unit.test_client_agent_agent_tool_watchers_support import *

def test_collect_claude_code_watch_events_hardlinks_transcript_to_global_resume_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    transcript_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "-workspace-project"
        / f"{session_id}.jsonl"
    )
    transcript_file.parent.mkdir(parents=True)
    transcript_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {"role": "assistant", "content": "global claude"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    global_transcript_file = home / ".claude" / "projects" / "-workspace-project" / f"{session_id}.jsonl"
    assert len(events) == 1
    assert global_transcript_file.samefile(transcript_file)

def test_collect_claude_code_watch_events_enriches_subagent_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    transcript_dir = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "-workspace-project"
    )
    main_file = transcript_dir / f"{session_id}.jsonl"
    subagent_file = transcript_dir / "subagents" / "agent-subagent-1.jsonl"
    subagent_meta = transcript_dir / "subagents" / "agent-subagent-1.meta.json"
    subagent_file.parent.mkdir(parents=True)
    main_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-subagent-1",
                            "name": "Agent",
                            "input": {"description": "Return one", "prompt": "Return exactly: 1"},
                        }
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subagent_file.write_text(
        json.dumps(
            {
                "type": "user",
                "sessionId": session_id,
                "agentId": "subagent-1",
                "isSidechain": True,
                "message": {"role": "user", "content": "Return exactly: 1"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subagent_meta.write_text(
        json.dumps({"agentType": "claude", "description": "Return one", "toolUseId": "call-subagent-1"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(events) == 2
    main_event = next(event for event in events if event.source_path == str(main_file))
    subagent_event = next(event for event in events if event.source_path == str(subagent_file))
    assert main_event.payload["subagent_tool_use_results"] == [
        {
            "agent_id": "subagent-1",
            "tool_use_id": "call-subagent-1",
            "source_path": str(subagent_file),
        }
    ]
    assert subagent_event.payload["subagent"]["toolUseId"] == "call-subagent-1"
    assert subagent_event.payload["agentId"] == "subagent-1"
    assert subagent_event.payload["isSidechain"] is True

def test_read_claude_history_session_ids_extracts_sessions_and_tracks_offset(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    history_file.write_text(
        json.dumps({"display": "hi", "sessionId": "claude-session-1"}) + "\n"
        + json.dumps({"display": "missing session"}) + "\n",
        encoding="utf-8",
    )

    session_ids, offset = read_claude_history_session_ids(history_file, 0)
    second_session_ids, second_offset = read_claude_history_session_ids(history_file, offset)

    assert session_ids == {"claude-session-1"}
    assert offset == history_file.stat().st_size
    assert second_session_ids == set()
    assert second_offset == offset

def test_read_all_claude_history_session_ids_reads_past_default_batch_limit(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    history_file.write_text(
        "".join(
            json.dumps({"display": f"prompt {index}", "sessionId": f"claude-session-{index}"}) + "\n"
            for index in range(125)
        ),
        encoding="utf-8",
    )

    session_ids = read_all_claude_history_session_ids(history_file)

    assert len(session_ids) == 125
    assert "claude-session-0" in session_ids
    assert "claude-session-124" in session_ids

def test_collect_claude_code_watch_events_maps_history_session_to_managed_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    history_file = home / ".web-terminal-acp" / "claude-code-homes" / str(WINDOW_ID) / "history.jsonl"
    transcript_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "-workspace-project"
        / f"{session_id}.jsonl"
    )
    history_file.parent.mkdir(parents=True)
    transcript_file.parent.mkdir(parents=True)
    history_file.write_text(
        json.dumps({"display": "fix bug", "sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    transcript_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "mapped transcript"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_claude_code_watch_events(
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

    assert len(events) == 1
    event = events[0]
    assert event.provider == "claude_code"
    assert event.source_path == str(transcript_file)
    assert event.offset == 0
    assert event.cursor == 0
    assert event.payload["sessionId"] == session_id
    assert event.payload["message"]["content"][0]["text"] == "mapped transcript"
    assert event.payload["WEB_TERMINAL_CLIENT_ID"] == str(CLIENT_ID)
    assert event.payload["WEB_TERMINAL_WINDOW_ID"] == str(WINDOW_ID)
    assert event.payload["WEB_TERMINAL_PROJECT_PATH"] == "/workspace/project"
    assert second == []
    assert state.claude_code_history_session_ids == {session_id}
    assert state.claude_code_history_jsonl_files == {transcript_file}
    assert state.claude_code_offsets[transcript_file] == transcript_file.stat().st_size


def test_collect_claude_code_watch_events_adds_window_model_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    claude_home = home / ".web-terminal-acp" / "claude-code-homes" / str(WINDOW_ID)
    history_file = claude_home / "history.jsonl"
    transcript_file = claude_home / "projects" / "-workspace-project" / f"{session_id}.jsonl"
    transcript_file.parent.mkdir(parents=True)
    history_file.write_text(
        json.dumps({"display": "fix bug", "sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    (claude_home / "settings.json").write_text(
        json.dumps({"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "230000"}}),
        encoding="utf-8",
    )
    transcript_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 112838,
                        "output_tokens": 863,
                    },
                    "content": [{"type": "text", "text": "done"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(events) == 1
    assert events[0].payload["model_auto_compact_token_limit"] == 230000


def test_initialize_agent_tool_watcher_state_starts_linked_claude_history_at_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    history_file = home / ".web-terminal-acp" / "claude-code-homes" / str(WINDOW_ID) / "history.jsonl"
    transcript_file = (
        home
        / ".web-terminal-acp"
        / "claude-code-homes"
        / str(WINDOW_ID)
        / "projects"
        / "-workspace-project"
        / f"{session_id}.jsonl"
    )
    history_file.parent.mkdir(parents=True)
    transcript_file.parent.mkdir(parents=True)
    history_file.write_text(
        json.dumps({"display": "resume", "sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    transcript_file.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {"role": "assistant", "content": "old transcript"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    now = 1_780_000_000.0
    old = now - watchers.CLAUDE_ACTIVE_SESSION_BOOTSTRAP_SECONDS - 1
    os.utime(transcript_file, (old, old))
    monkeypatch.setattr(watchers.time, "time", lambda: now)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)

    assert state.claude_code_history_offset == history_file.stat().st_size
    assert state.claude_code_history_session_ids == set()
    assert state.claude_code_pending_history_session_ids == set()
    assert state.claude_code_history_jsonl_files == set()
    assert collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    ) == []

    new_history_offset = history_file.stat().st_size
    new_transcript_offset = transcript_file.stat().st_size
    history_file.write_text(
        history_file.read_text(encoding="utf-8")
        + json.dumps({"display": "continue", "sessionId": session_id})
        + "\n",
        encoding="utf-8",
    )
    transcript_file.write_text(
        transcript_file.read_text(encoding="utf-8")
        + json.dumps(
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {"role": "assistant", "content": "new transcript"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = collect_claude_code_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.offset for event in events] == [new_transcript_offset]
    assert events[0].payload["message"]["content"] == "new transcript"
    assert state.claude_code_history_offset > new_history_offset
    assert state.claude_code_history_session_ids == {session_id}

def test_collect_codex_watch_events_reuses_discovered_paths_until_refresh(
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
    calls: list[UUID] = []

    def discover(window_id: UUID) -> list[Path]:
        calls.append(window_id)
        return [session_file]

    monkeypatch.setattr("app.client_agent.agent_tool_watchers.iter_codex_session_files", discover)
    state = AgentToolWatcherState()

    collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert calls == [WINDOW_ID]

def test_collect_codex_watch_events_retries_empty_discovery_soon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    calls: list[UUID] = []
    recent_calls: list[UUID] = []
    now = 100.0

    def discover(window_id: UUID) -> list[Path]:
        calls.append(window_id)
        return []

    def discover_recent(window_id: UUID) -> list[Path]:
        recent_calls.append(window_id)
        return [session_file] if session_file.exists() else []

    monkeypatch.setattr(watchers.time, "monotonic", lambda: now)
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.iter_codex_session_files", discover)
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.iter_recent_codex_session_files", discover_recent)
    state = AgentToolWatcherState()

    assert collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    ) == []

    session_file.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "new codex session"}],
                },
                "timestamp": "2026-05-23T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    now = 101.0
    assert collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    ) == []
    assert calls == [WINDOW_ID]
    assert recent_calls == []

    now = 102.0
    events = collect_codex_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.source_path for event in events] == [str(session_file)]
    assert events[0].payload["payload"]["content"][0]["text"] == "new codex session"
    assert calls == [WINDOW_ID]
    assert recent_calls == [WINDOW_ID]

def test_collect_cursor_watch_events_finds_window_stores_and_tracks_seen_blobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    store = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "state" / "store.db"
    store.parent.mkdir(parents=True)
    write_cursor_store(store)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    first = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    second = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.provider for event in first] == ["cursor_cli", "cursor_cli"]
    assert [event.source_path for event in first] == [str(store), str(store)]
    assert [event.cursor for event in first] == ["root-1", "root-1"]
    assert state.cursor_store_paths == [store]
    assert second == []
    assert state.cursor_seen_blob_ids[store] == {"user-blob", "assistant-blob"}
    assert [event.payload["blob_id"] for event in first] == ["user-blob", "assistant-blob"]
    assert all(event.payload["client_id"] == str(CLIENT_ID) for event in first)
    assert all(event.payload["virtual_window_id"] == str(WINDOW_ID) for event in first)
    assert all(event.payload["project_path"] == "/workspace/project" for event in first)
