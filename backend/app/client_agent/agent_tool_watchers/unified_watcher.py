from __future__ import annotations

# ruff: noqa: F821

from importlib import import_module

_event_dispatch = import_module("app.client_agent.agent_tool_watchers.event_dispatch")

globals().update(
    {name: value for name, value in _event_dispatch.__dict__.items() if not name.startswith("__")}
)

class UnifiedAgentToolWatcher:
    def __init__(
        self,
        send_event: ManagedEventSender,
        client_id: UUID,
        *,
        send_presence: PresenceEventSender | None = None,
        terminal: ClientTerminalMultiplexer | None = None,
        runtime: ClientTmuxRuntime | None = None,
        idle_supervisor: AgentIdleSupervisor | None = None,
        stale_window_cleanup: ClientStaleWindowCleanup | None = None,
    ) -> None:
        self._send_event = send_event
        self._client_id = client_id
        self._send_presence = send_presence
        self._terminal = terminal
        self._runtime = runtime
        self._idle_supervisor = idle_supervisor
        self._stale_window_cleanup = stale_window_cleanup
        self._windows: dict[UUID, AgentToolWatchWindow] = {}
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._process_scan_interval = max(
            PRESENCE_SEND_INTERVAL_SECONDS,
            AGENT_WATCH_PROCESS_SCAN_INTERVAL_SECONDS,
        )

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("unified agent tool watcher is closed")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    def watch_window(
        self,
        window_id: UUID,
        project_path: str | None,
        *,
        providers: frozenset[str] | set[str] | None = None,
    ) -> None:
        provider_filter = _normalize_provider_filter(providers)
        existing = self._windows.get(window_id)
        if existing is not None:
            existing.project_path = project_path
            existing.providers = provider_filter
            self._wakeup.set()
            return

        now = time.perf_counter()
        self._windows[window_id] = AgentToolWatchWindow(
            window_id=window_id,
            project_path=project_path,
            providers=provider_filter,
            next_event_scan_at=now,
            next_process_scan_at=now
            + _initial_process_scan_delay(window_id, self._process_scan_interval),
        )
        self._wakeup.set()

    def remove_window(self, window_id: UUID) -> None:
        self._windows.pop(window_id, None)
        self._wakeup.set()

    async def close(self) -> None:
        self._closed = True
        self._wakeup.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            window = self._next_due_window()
            if window is None:
                await self._wait_for_due_window()
                continue
            try:
                await self._scan_window(window)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "client-agent unified agent watcher scan failed",
                    extra={
                        "client_id": str(self._client_id),
                        "window_id": str(window.window_id),
                    },
                )
                if self._windows.get(window.window_id) is window:
                    retry_at = time.perf_counter() + AGENT_WATCH_IDLE_INTERVAL_SECONDS
                    window.next_event_scan_at = retry_at
                    window.next_process_scan_at = max(window.next_process_scan_at, retry_at)

    def _next_due_window(self) -> AgentToolWatchWindow | None:
        if not self._windows:
            return None
        now = time.perf_counter()
        due_windows = [
            window
            for window in self._windows.values()
            if window.next_event_scan_at <= now or window.next_process_scan_at <= now
        ]
        if not due_windows:
            return None
        return min(due_windows, key=self._next_due_at)

    def _next_due_at(self, window: AgentToolWatchWindow) -> float:
        return min(window.next_event_scan_at, window.next_process_scan_at)

    async def _wait_for_due_window(self) -> None:
        self._wakeup.clear()
        if not self._windows:
            await self._wakeup.wait()
            return
        now = time.perf_counter()
        timeout = max(0.0, min(self._next_due_at(window) for window in self._windows.values()) - now)
        try:
            await asyncio.wait_for(self._wakeup.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    async def _scan_window(self, window: AgentToolWatchWindow) -> None:
        window_id = window.window_id
        started_at = time.perf_counter()
        managed_sent_count = 0
        presence_sent_count = 0

        if not window.initialized:
            await _run_watcher_scan(
                initialize_agent_tool_watcher_state,
                window.state,
                window_id=window_id,
            )
            if self._windows.get(window_id) is not window:
                return
            window.initialized = True

        now = time.perf_counter()
        event_scan_due = now >= window.next_event_scan_at
        process_scan_due = now >= window.next_process_scan_at

        if event_scan_due:
            managed_events = await _run_watcher_scan(
                _collect_all_events,
                window.state,
                client_id=self._client_id,
                window_id=window_id,
                project_path=window.project_path,
                providers=window.providers,
            )
            if self._windows.get(window_id) is not window:
                return
            if self._idle_supervisor is not None and managed_events:
                await self._idle_supervisor.observe_events(managed_events)
            if self._stale_window_cleanup is not None and managed_events:
                self._stale_window_cleanup.touch_window(window_id)
        else:
            managed_events = []

        if self._windows.get(window_id) is not window:
            return

        now = time.perf_counter()
        process_scan_due = now >= window.next_process_scan_at
        if self._idle_supervisor is not None and process_scan_due:
            await self._idle_supervisor.maybe_suspend_window(window_id)

        if self._send_presence is not None and process_scan_due:
            presence = await detect_agent_work_presence(
                window_id,
                terminal=self._terminal,
                runtime=self._runtime,
            )
            if presence is not None:
                if self._stale_window_cleanup is not None:
                    self._stale_window_cleanup.touch_window(window_id)
                await self._send_presence(
                    AgentMessage(
                        type="agent_work_presence",
                        client_id=self._client_id,
                        window_id=window_id,
                        payload={
                            "providers": list(presence.providers),
                            "reasons": list(presence.reasons),
                        },
                    )
                )
                presence_sent_count += 1

        if self._windows.get(window_id) is not window:
            return

        for event in managed_events:
            if await enqueue_managed_ai_event(self._send_event, event):
                managed_sent_count += 1

        if self._windows.get(window_id) is not window:
            return

        if event_scan_due:
            if managed_sent_count:
                window.sleep_seconds = AGENT_WATCH_ACTIVE_INTERVAL_SECONDS
            else:
                window.sleep_seconds = min(
                    AGENT_WATCH_MAX_INTERVAL_SECONDS,
                    max(AGENT_WATCH_IDLE_INTERVAL_SECONDS, window.sleep_seconds * 1.5),
                )
            window.next_event_scan_at = time.perf_counter() + window.sleep_seconds

        if process_scan_due:
            window.next_process_scan_at = time.perf_counter() + self._process_scan_interval

        elapsed = time.perf_counter() - started_at
        if elapsed >= AGENT_WATCH_SLOW_SCAN_SECONDS and started_at >= window.next_slow_scan_warning_at:
            window.next_slow_scan_warning_at = (
                started_at + AGENT_WATCH_SLOW_SCAN_WARNING_INTERVAL_SECONDS
            )
            logger.warning(
                "client-agent unified agent watcher scan was slow",
                extra={
                    "client_id": str(self._client_id),
                    "window_id": str(window_id),
                    "managed_event_count": managed_sent_count,
                    "presence_event_count": presence_sent_count,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )


def initialize_agent_tool_watcher_state(state: AgentToolWatcherState, *, window_id: UUID) -> None:
    state.codex_session_files = iter_codex_session_files(window_id)
    state.codex_session_files_refreshed_at = time.monotonic()
    state.codex_recent_session_files_refreshed_at = state.codex_session_files_refreshed_at
    bootstrap_codex_path = None
    if not _is_cloned_codex_home(window_id):
        bootstrap_codex_path = _recent_latest_codex_session_file(state.codex_session_files)
    for path in state.codex_session_files:
        try:
            state.codex_offsets[path] = 0 if path == bootstrap_codex_path else _jsonl_tail_resume_offset(path)
        except FileNotFoundError:
            state.codex_offsets.pop(path, None)

    state.claude_code_jsonl_files = iter_claude_code_jsonl_files(window_id)
    state.claude_code_jsonl_files_refreshed_at = time.monotonic()
    bootstrap_claude_paths = _recent_claude_code_session_files(state.claude_code_jsonl_files)
    for path in state.claude_code_jsonl_files:
        try:
            state.claude_code_offsets[path] = (
                0 if path in bootstrap_claude_paths else _jsonl_tail_resume_offset(path)
            )
        except FileNotFoundError:
            state.claude_code_offsets.pop(path, None)
    history_file = claude_code_history_file(window_id)
    try:
        state.claude_code_history_offset = _jsonl_tail_resume_offset(history_file)
    except FileNotFoundError:
        state.claude_code_history_offset = 0

    state.cursor_store_paths = cursor_store_paths_for_window(window_id)
    for path in state.cursor_store_paths:
        state.cursor_last_rowids[path] = _cursor_store_max_rowid(path)
        state.cursor_seen_blob_ids.setdefault(path, set())
    state.cursor_discovery_started = True

    state.antigravity_transcript_files = iter_antigravity_transcript_files(window_id)
    state.antigravity_transcript_files_refreshed_at = time.monotonic()
    bootstrap_antigravity_path = _recent_latest_antigravity_transcript_file(
        state.antigravity_transcript_files
    )
    for path in state.antigravity_transcript_files:
        try:
            state.antigravity_offsets[path] = 0 if path == bootstrap_antigravity_path else _jsonl_tail_resume_offset(path)
        except FileNotFoundError:
            state.antigravity_offsets.pop(path, None)


def _recent_latest_codex_session_file(paths: list[Path]) -> Path | None:
    latest_path: Path | None = None
    latest_mtime = 0.0
    now = time.time()
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        if now - stat.st_mtime > CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS:
            continue
        if latest_path is None or stat.st_mtime > latest_mtime:
            latest_path = path
            latest_mtime = stat.st_mtime
    return latest_path


def _is_cloned_codex_home(window_id: UUID | str) -> bool:
    return (codex_sessions_dir(window_id).parent / CODEX_CLONE_MARKER).exists()


def _recent_latest_antigravity_transcript_file(paths: list[Path]) -> Path | None:
    return _recent_latest_codex_session_file(paths)


def _recent_claude_code_session_files(paths: list[Path]) -> set[Path]:
    recent_paths: set[Path] = set()
    now = time.time()
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        if now - stat.st_mtime <= CLAUDE_ACTIVE_SESSION_BOOTSTRAP_SECONDS:
            recent_paths.add(path)
    return recent_paths


def _jsonl_tail_resume_offset(path: Path) -> int:
    size = path.stat().st_size
    if size == 0:
        return 0

    with path.open("rb") as handle:
        handle.seek(size - 1)
        if handle.read(1) == b"\n":
            return size

        cursor = size
        while cursor > 0:
            chunk_size = min(8192, cursor)
            cursor -= chunk_size
            handle.seek(cursor)
            chunk = handle.read(chunk_size)
            newline_index = chunk.rfind(b"\n")
            if newline_index >= 0:
                return cursor + newline_index + 1
    return 0


def _cursor_store_max_rowid(path: Path) -> int:
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.DatabaseError:
        return 0
    try:
        try:
            row = conn.execute("select max(rowid) from blobs").fetchone()
        except sqlite3.DatabaseError:
            return 0
        value = row[0] if row is not None else None
        return int(value) if value is not None else 0
    finally:
        conn.close()


def _cached_codex_session_files(state: AgentToolWatcherState, window_id: UUID) -> list[Path]:
    now = time.monotonic()
    if state.codex_session_files_refreshed_at == 0.0 or (
        now - state.codex_session_files_refreshed_at >= AGENT_WATCH_DISCOVERY_INTERVAL_SECONDS
    ):
        state.codex_session_files = iter_codex_session_files(window_id)
        state.codex_session_files_refreshed_at = now
        state.codex_recent_session_files_refreshed_at = now
    elif now - state.codex_recent_session_files_refreshed_at >= CODEX_RECENT_DISCOVERY_INTERVAL_SECONDS:
        _merge_codex_session_files(
            state,
            iter_recent_codex_session_files(window_id),
        )
        state.codex_recent_session_files_refreshed_at = now
    return state.codex_session_files


def _merge_codex_session_files(state: AgentToolWatcherState, paths: list[Path]) -> None:
    known_paths = set(state.codex_session_files)
    for path in paths:
        if path not in known_paths:
            state.codex_session_files.append(path)
            known_paths.add(path)
    state.codex_session_files.sort()


def _cached_claude_code_jsonl_files(state: AgentToolWatcherState, window_id: UUID) -> list[Path]:
    now = time.monotonic()
    if state.claude_code_jsonl_files_refreshed_at == 0.0 or (
        now - state.claude_code_jsonl_files_refreshed_at >= AGENT_WATCH_DISCOVERY_INTERVAL_SECONDS
    ):
        state.claude_code_jsonl_files = iter_claude_code_jsonl_files(window_id)
        state.claude_code_jsonl_files_refreshed_at = now
    return sorted({*state.claude_code_jsonl_files, *state.claude_code_history_jsonl_files})


def _cached_antigravity_transcript_files(state: AgentToolWatcherState, window_id: UUID) -> list[Path]:
    now = time.monotonic()
    if state.antigravity_transcript_files_refreshed_at == 0.0 or (
        now - state.antigravity_transcript_files_refreshed_at >= AGENT_WATCH_DISCOVERY_INTERVAL_SECONDS
    ):
        known_paths = set(state.antigravity_transcript_files)
        for path in iter_antigravity_transcript_files(window_id):
            if path not in known_paths:
                state.antigravity_transcript_files.append(path)
                state.antigravity_offsets.setdefault(path, 0)
                known_paths.add(path)
        state.antigravity_transcript_files_refreshed_at = now
    return state.antigravity_transcript_files


def _refresh_claude_code_history_sessions(state: AgentToolWatcherState, window_id: UUID) -> None:
    history_file = claude_code_history_file(window_id)
    offset = state.claude_code_history_offset
    try:
        session_ids, next_offset = read_claude_history_session_ids(history_file, offset)
    except FileNotFoundError:
        state.claude_code_history_offset = 0
        return

    state.claude_code_history_offset = next_offset
    new_pending_session_ids = session_ids - state.claude_code_history_session_ids
    state.claude_code_pending_history_session_ids.update(new_pending_session_ids)
    if not state.claude_code_pending_history_session_ids:
        return

    now = time.monotonic()
    pending_retry_due = (
        state.claude_code_pending_history_scanned_at == 0.0
        or now - state.claude_code_pending_history_scanned_at >= CLAUDE_HISTORY_PENDING_RETRY_SECONDS
    )
    if not new_pending_session_ids and not pending_retry_due:
        return
    state.claude_code_pending_history_scanned_at = now

    found_session_ids = _add_claude_code_history_transcripts(
        state,
        window_id=window_id,
        session_ids=state.claude_code_pending_history_session_ids,
        start_at_eof=False,
    )
    if found_session_ids:
        state.claude_code_pending_history_session_ids.difference_update(found_session_ids)
        state.claude_code_history_session_ids.update(found_session_ids)


def _add_claude_code_history_transcripts(
    state: AgentToolWatcherState,
    *,
    window_id: UUID,
    session_ids: set[str],
    start_at_eof: bool,
) -> set[str]:
    found_session_ids: set[str] = set()
    for session_id in sorted(session_ids):
        for path in iter_claude_code_transcript_files_for_session(window_id, session_id):
            if path not in state.claude_code_history_jsonl_files:
                state.claude_code_history_jsonl_files.add(path)
                if start_at_eof:
                    try:
                        state.claude_code_offsets.setdefault(path, path.stat().st_size)
                    except FileNotFoundError:
                        state.claude_code_offsets.pop(path, None)
                        continue
                else:
                    state.claude_code_offsets.setdefault(path, 0)
            found_session_ids.add(session_id)
    return found_session_ids


def read_claude_history_session_ids(path: Path, offset: int) -> tuple[set[str], int]:
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if offset > path.stat().st_size:
        offset = 0
    entries, next_offset = read_new_jsonl_events(path, offset)
    return {
        session_id
        for entry, _line_offset in entries
        if (session_id := _claude_history_session_id(entry)) is not None
    }, next_offset


def read_all_claude_history_session_ids(path: Path) -> set[str]:
    session_ids: set[str] = set()
    offset = 0
    while True:
        batch_session_ids, next_offset = read_claude_history_session_ids(path, offset)
        session_ids.update(batch_session_ids)
        if next_offset == offset or next_offset >= path.stat().st_size:
            return session_ids
        offset = next_offset


def _claude_history_session_id(entry: dict[str, Any]) -> str | None:
    value = entry.get("sessionId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


__all__ = [name for name in globals() if not name.startswith("__")]
