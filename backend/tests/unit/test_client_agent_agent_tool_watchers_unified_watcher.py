# ruff: noqa: F403,F405

import logging

from tests.unit.test_client_agent_agent_tool_watchers_support import *

def test_initialize_agent_tool_watcher_state_starts_cursor_collector_after_existing_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    store = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "state" / "store.db"
    store.parent.mkdir(parents=True)
    write_cursor_store(store)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)

    assert collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    ) == []

    append_cursor_blob(store, "new-assistant-blob", "assistant", "new cursor")
    events = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.payload["blob_id"] for event in events] == ["new-assistant-blob"]
    assert events[0].payload["text"] == "new cursor"

def test_collect_cursor_watch_events_discovers_store_created_after_initial_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    assert collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    ) == []

    store = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "state" / "store.db"
    store.parent.mkdir(parents=True)
    write_cursor_store(store)

    events = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert events == []
    assert state.cursor_store_paths == [store]
    assert state.cursor_last_rowids[store] == 3

    append_cursor_blob(store, "new-assistant-blob", "assistant", "new cursor")
    events = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.payload["blob_id"] for event in events] == ["new-assistant-blob"]
    assert events[0].payload["text"] == "new cursor"

@pytest.mark.asyncio
async def test_watch_agent_tool_events_notifies_idle_supervisor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_file = tmp_path / "rollout-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    session_file.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.iter_codex_session_files",
        lambda window_id: [session_file],
    )
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )

    supervisor = FakeIdleSupervisor()
    sent: list[object] = []

    async def send_event(message):
        sent.append(message)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await watch_agent_tool_events(
            send_event,
            CLIENT_ID,
            WINDOW_ID,
            "/workspace/project",
            idle_supervisor=supervisor,
        )

    assert len(supervisor.observed_batches) == 1
    assert supervisor.observed_batches[0][0].provider == "codex"

@pytest.mark.asyncio
async def test_watch_agent_tool_events_defers_idle_and_presence_checks_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [])
    presence_calls: list[UUID] = []

    async def detect_presence(window_id, *, terminal, runtime):
        presence_calls.append(window_id)
        return None

    async def send_presence(_message):
        raise AssertionError("presence should not be sent during the first watcher loop")

    async def stop_after_first_loop(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr("app.client_agent.agent_tool_watchers.detect_agent_work_presence", detect_presence)
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.asyncio.sleep", stop_after_first_loop)

    supervisor = FakeIdleSupervisor()

    with pytest.raises(asyncio.CancelledError):
        await watch_agent_tool_events(
            lambda _message: asyncio.sleep(0),
            CLIENT_ID,
            WINDOW_ID,
            "/workspace/project",
            send_presence=send_presence,
            idle_supervisor=supervisor,
        )

    assert supervisor.checked_windows == []
    assert presence_calls == []

@pytest.mark.asyncio
async def test_watch_agent_tool_events_sends_presence_when_staggered_scan_is_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._initial_process_scan_delay", lambda window_id, interval: 0.0)

    class Signal:
        providers = ("codex",)
        reasons = ("process",)

    async def detect_presence(window_id, *, terminal, runtime):
        assert window_id == WINDOW_ID
        return Signal()

    sent_presence: list[AgentMessage] = []

    async def send_presence(message: AgentMessage):
        sent_presence.append(message)

    async def stop_after_first_loop(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr("app.client_agent.agent_tool_watchers.detect_agent_work_presence", detect_presence)
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.asyncio.sleep", stop_after_first_loop)

    supervisor = FakeIdleSupervisor()

    with pytest.raises(asyncio.CancelledError):
        await watch_agent_tool_events(
            lambda _message: asyncio.sleep(0),
            CLIENT_ID,
            WINDOW_ID,
            "/workspace/project",
            send_presence=send_presence,
            idle_supervisor=supervisor,
        )

    assert supervisor.checked_windows == [WINDOW_ID]
    assert len(sent_presence) == 1
    assert sent_presence[0].type == "agent_work_presence"
    assert sent_presence[0].payload == {"providers": ["codex"], "reasons": ["process"]}

@pytest.mark.asyncio
async def test_watcher_scans_are_concurrency_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchers, "AGENT_WATCH_COLLECTION_CONCURRENCY", 1)
    monkeypatch.setattr(watchers, "_WATCH_COLLECTION_SEMAPHORE", None)
    monkeypatch.setattr(watchers, "_WATCH_COLLECTION_SEMAPHORE_LOOP", None)
    entered: list[str] = []
    first_entered = threading.Event()
    release_first = threading.Event()

    def blocking_scan(name: str) -> str:
        entered.append(name)
        if name == "first":
            first_entered.set()
            release_first.wait(timeout=2)
        return name

    first = asyncio.create_task(watchers._run_watcher_scan(blocking_scan, "first"))
    assert await asyncio.to_thread(first_entered.wait, 1)
    second = asyncio.create_task(watchers._run_watcher_scan(blocking_scan, "second"))

    await asyncio.sleep(0.05)
    assert entered == ["first"]

    release_first.set()
    assert await first == "first"
    assert await second == "second"
    assert entered == ["first", "second"]

@pytest.mark.asyncio
async def test_unified_agent_tool_watcher_manages_multiple_windows_with_one_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [])

    scanned_windows: list[UUID] = []
    original_scan_window = UnifiedAgentToolWatcher._scan_window

    async def scan_once(self, window):
        scanned_windows.append(window.window_id)
        if len(scanned_windows) >= 2:
            raise asyncio.CancelledError
        await original_scan_window(self, window)

    monkeypatch.setattr(UnifiedAgentToolWatcher, "_scan_window", scan_once)

    watcher = UnifiedAgentToolWatcher(lambda _message: asyncio.sleep(0), CLIENT_ID)
    watcher.start()
    first_task = watcher._task
    other_window_id = UUID("11111111-2222-3333-4444-555555555555")
    watcher.watch_window(WINDOW_ID, "/workspace/one")
    watcher.watch_window(other_window_id, "/workspace/two")
    assert watcher._task is first_task

    with pytest.raises(asyncio.CancelledError):
        await first_task

    assert scanned_windows == [WINDOW_ID, other_window_id]

@pytest.mark.asyncio
async def test_unified_agent_tool_watcher_sends_presence_before_agent_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._initial_process_scan_delay", lambda window_id, interval: 0.0)

    from app.client_agent.ai_events import ManagedAiEvent

    event = ManagedAiEvent(
        provider="cursor_cli",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        source_path="/tmp/store.db",
        offset=None,
        cursor="root-1",
        project_path="/workspace/project",
        payload={
            "client_id": str(CLIENT_ID),
            "virtual_window_id": str(WINDOW_ID),
            "agentId": "cursor-agent-1",
            "blob_id": "assistant-blob",
            "role": "assistant",
            "text": "hello",
        },
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [event])

    class Signal:
        providers = ("cursor_cli",)
        reasons = ("process",)

    async def detect_presence(window_id, *, terminal, runtime):
        return Signal()

    monkeypatch.setattr("app.client_agent.agent_tool_watchers.detect_agent_work_presence", detect_presence)

    sent: list[AgentMessage] = []

    async def send(message: AgentMessage):
        sent.append(message)
        if len(sent) == 2:
            raise asyncio.CancelledError

    watcher = UnifiedAgentToolWatcher(send, CLIENT_ID, send_presence=send)
    watcher.watch_window(WINDOW_ID, "/workspace/project")

    with pytest.raises(asyncio.CancelledError):
        await watcher._run()

    assert [message.type for message in sent] == ["agent_work_presence", "ai_event"]


@pytest.mark.asyncio
async def test_unified_agent_tool_watcher_marks_cleanup_activity_for_agent_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.client_agent.agent_tool_watchers.initialize_agent_tool_watcher_state",
        lambda state, *, window_id: None,
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._initial_process_scan_delay", lambda window_id, interval: 0.0)

    from app.client_agent.ai_events import ManagedAiEvent

    event = ManagedAiEvent(
        provider="codex",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        source_path="/tmp/session.jsonl",
        offset=1,
        cursor=None,
        project_path="/workspace/project",
        payload={
            "WEB_TERMINAL_CLIENT_ID": str(CLIENT_ID),
            "WEB_TERMINAL_WINDOW_ID": str(WINDOW_ID),
            "type": "message",
            "role": "assistant",
        },
    )
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [event])
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.detect_agent_work_presence", lambda *args, **kwargs: None)

    class Cleanup:
        def __init__(self) -> None:
            self.touched: list[UUID] = []

        def touch_window(self, window_id: UUID) -> None:
            self.touched.append(window_id)

    cleanup = Cleanup()
    sent: list[AgentMessage] = []

    async def send(message: AgentMessage):
        sent.append(message)
        raise asyncio.CancelledError

    watcher = UnifiedAgentToolWatcher(send, CLIENT_ID, stale_window_cleanup=cleanup)
    watcher.watch_window(WINDOW_ID, "/workspace/project")

    with pytest.raises(asyncio.CancelledError):
        await watcher._run()

    assert cleanup.touched == [WINDOW_ID]
    assert sent[0].type == "ai_event"


@pytest.mark.asyncio
async def test_unified_agent_tool_watcher_keeps_running_after_window_scan_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.AGENT_WATCH_IDLE_INTERVAL_SECONDS", 0.01)
    scanned_windows: list[UUID] = []
    other_window_id = UUID("11111111-2222-3333-4444-555555555555")

    async def scan_window(self, window):
        scanned_windows.append(window.window_id)
        if window.window_id == WINDOW_ID:
            raise RuntimeError("boom")
        raise asyncio.CancelledError

    monkeypatch.setattr(UnifiedAgentToolWatcher, "_scan_window", scan_window)
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.time.perf_counter", lambda: 100.0)

    watcher = UnifiedAgentToolWatcher(lambda _message: asyncio.sleep(0), CLIENT_ID)
    watcher.watch_window(WINDOW_ID, "/workspace/one")
    watcher.watch_window(other_window_id, "/workspace/two")

    with pytest.raises(asyncio.CancelledError):
        await watcher._run()

    assert scanned_windows == [WINDOW_ID, other_window_id]


@pytest.mark.asyncio
async def test_unified_agent_tool_watcher_throttles_repeated_slow_scan_warnings(
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    monkeypatch.setattr("app.client_agent.agent_tool_watchers._collect_all_events", lambda *args, **kwargs: [])
    times = iter([0, 0, 0, 0, 2, 10, 10, 10, 10, 12, 61, 61, 61, 61, 63])
    monkeypatch.setattr("app.client_agent.agent_tool_watchers.time.perf_counter", lambda: next(times))
    window = watchers.AgentToolWatchWindow(WINDOW_ID, "/workspace/project")
    window.initialized = True
    window.next_process_scan_at = 1000.0
    watcher = UnifiedAgentToolWatcher(lambda _message: asyncio.sleep(0), CLIENT_ID)
    watcher._windows[WINDOW_ID] = window

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            window.next_event_scan_at = 0.0
            await watcher._scan_window(window)

    assert caplog.text.count("client-agent unified agent watcher scan was slow") == 2

def test_collect_cursor_watch_events_finds_managed_cursor_data_dir_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    store = (
        home
        / ".web-terminal-acp"
        / "cursor-homes"
        / str(WINDOW_ID)
        / "chats"
        / "workspace-hash"
        / "session-id"
        / "store.db"
    )
    store.parent.mkdir(parents=True)
    write_cursor_store(store)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    events = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.source_path for event in events] == [str(store), str(store)]
    assert state.cursor_store_paths == [store]

def test_cursor_store_paths_for_window_reads_linked_chats_and_repairs_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    source_chats = home / ".cursor" / "chats"
    store = source_chats / "workspace-hash" / "session-id" / "store.db"
    managed_chats = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "chats"
    store.parent.mkdir(parents=True)
    write_cursor_store(store)
    managed_chats.parent.mkdir(parents=True)
    managed_chats.symlink_to(source_chats)
    monkeypatch.setattr(Path, "home", lambda: home)

    assert watchers.cursor_store_paths_for_window(WINDOW_ID) == [store]
    assert managed_chats.is_dir()
    assert not managed_chats.is_symlink()
