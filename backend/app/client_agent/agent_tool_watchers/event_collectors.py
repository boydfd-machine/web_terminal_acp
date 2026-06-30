from __future__ import annotations

# ruff: noqa: F821

from importlib import import_module

from app.client_agent.cursor_statusline import collect_cursor_statusline_watch_events

_watch_state = import_module("app.client_agent.agent_tool_watchers.watch_state")

globals().update(
    {name: value for name, value in _watch_state.__dict__.items() if not name.startswith("__")}
)


def collect_codex_watch_events(
    state: AgentToolWatcherState,
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
) -> list[ManagedAiEvent]:
    events: list[ManagedAiEvent] = []
    for path in _cached_codex_session_files(state, window_id):
        sync_codex_session_file_to_global(window_id, path)
        offset = state.codex_offsets.get(path, 0)
        try:
            if offset > path.stat().st_size:
                offset = 0
            payloads, next_offset = read_new_codex_events(
                path,
                offset,
                client_id=client_id,
                window_id=window_id,
            )
        except FileNotFoundError:
            state.codex_offsets.pop(path, None)
            continue
        state.codex_offsets[path] = next_offset
        for payload, line_offset in payloads:
            payload["project_path"] = project_path
            events.append(
                ManagedAiEvent(
                    provider="codex",
                    client_id=client_id,
                    window_id=window_id,
                    source_path=str(path),
                    offset=line_offset,
                    cursor=line_offset,
                    project_path=project_path,
                    payload=payload,
                )
            )
    return events


def collect_claude_code_watch_events(
    state: AgentToolWatcherState,
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
) -> list[ManagedAiEvent]:
    _refresh_claude_code_history_sessions(state, window_id)
    subagent_results_by_tool_use_id = _claude_subagent_result_index(window_id)
    model_metadata = agent_config_service.window_agent_model_metadata(
        "claude",
        window_id=str(window_id),
    )
    events: list[ManagedAiEvent] = []
    for path in _cached_claude_code_jsonl_files(state, window_id):
        sync_claude_code_transcript_file_to_global(window_id, path)
        subagent_meta = _read_claude_subagent_meta(path)
        path_subagent_id = _subagent_id_from_path(path)
        offset = state.claude_code_offsets.get(path, 0)
        try:
            if offset > path.stat().st_size:
                offset = 0
            payloads, next_offset = read_new_jsonl_events(path, offset)
        except FileNotFoundError:
            state.claude_code_offsets.pop(path, None)
            continue
        state.claude_code_offsets[path] = next_offset
        for payload, line_offset in payloads:
            payload.setdefault("WEB_TERMINAL_CLIENT_ID", str(client_id))
            payload.setdefault("WEB_TERMINAL_WINDOW_ID", str(window_id))
            payload.setdefault("WEB_TERMINAL_PROJECT_PATH", project_path or "")
            _attach_model_metadata(payload, model_metadata)
            if subagent_meta is not None:
                payload.setdefault("subagent", subagent_meta)
                payload.setdefault("agentId", path_subagent_id or subagent_meta.get("agentId") or subagent_meta.get("agent_id"))
                payload.setdefault("isSidechain", True)
            _attach_claude_subagent_call_matches(payload, subagent_results_by_tool_use_id)
            events.append(
                ManagedAiEvent(
                    provider="claude_code",
                    client_id=client_id,
                    window_id=window_id,
                    source_path=str(path),
                    offset=line_offset,
                    cursor=line_offset,
                    project_path=project_path,
                    payload=payload,
                )
            )
    return events


def _attach_model_metadata(payload: dict[str, Any], metadata: dict[str, object] | None) -> None:
    if metadata is None:
        return
    _set_payload_default(payload, "model_context_window", metadata.get("context_window"))
    _set_payload_default(payload, "model_auto_compact_token_limit", metadata.get("auto_compact_token_limit"))


def _set_payload_default(payload: dict[str, Any], key: str, value: object) -> None:
    if isinstance(value, int) and value >= 0:
        payload.setdefault(key, value)


def _attach_claude_subagent_call_matches(
    payload: dict[str, Any],
    matches_by_tool_use_id: dict[str, list[dict[str, str]]],
) -> None:
    content = payload.get("message")
    if isinstance(content, dict):
        content = content.get("content")
    if not isinstance(content, list):
        return
    matches: list[dict[str, str]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use" or block.get("name") != "Agent":
            continue
        tool_use_id = block.get("id")
        if not isinstance(tool_use_id, str):
            continue
        matches.extend(matches_by_tool_use_id.get(tool_use_id, []))
    if matches:
        payload.setdefault("subagent_tool_use_results", matches)


def read_new_jsonl_events(
    path: Path,
    offset: int,
    *,
    max_events: int = 100,
) -> tuple[list[tuple[dict[str, Any], int]], int]:
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if max_events < 1:
        raise ValueError("max_events must be at least 1")

    events: list[tuple[dict[str, Any], int]] = []
    next_offset = offset
    with path.open("rb") as handle:
        handle.seek(offset)
        while len(events) < max_events:
            line_offset = handle.tell()
            raw_line = handle.readline()
            if not raw_line:
                next_offset = handle.tell()
                break
            if not raw_line.endswith(b"\n"):
                next_offset = line_offset
                break

            next_offset = handle.tell()
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("Skipping invalid Claude Code JSONL line", extra={"path": str(path), "offset": line_offset})
                continue
            if isinstance(payload, dict):
                events.append((payload, line_offset))
    return events, next_offset


def collect_cursor_watch_events(
    state: AgentToolWatcherState,
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
) -> list[ManagedAiEvent]:
    known_paths = set(state.cursor_store_paths)
    for path in cursor_store_paths_for_window(window_id):
        if path not in known_paths:
            state.cursor_store_paths.append(path)
            known_paths.add(path)
            if state.cursor_discovery_started:
                state.cursor_last_rowids[path] = _cursor_store_max_rowid(path)
            state.cursor_seen_blob_ids.setdefault(path, set())
    state.cursor_discovery_started = True

    events: list[ManagedAiEvent] = []
    for payload in collect_cursor_statusline_watch_events(
        state=state,
        client_id=client_id,
        window_id=window_id,
        project_path=project_path,
    ):
        events.append(
            ManagedAiEvent(
                provider="cursor_cli",
                client_id=client_id,
                window_id=window_id,
                source_path=payload.get("source_path"),
                offset=None,
                cursor=payload.get("session_id"),
                project_path=project_path,
                payload=payload,
            )
        )
    for path in state.cursor_store_paths:
        seen = state.cursor_seen_blob_ids.setdefault(path, set())
        after_rowid = state.cursor_last_rowids.get(path, 0)
        try:
            payloads, root_blob_id, max_rowid = read_cursor_store_events(
                path,
                seen_blob_ids=seen,
                after_rowid=after_rowid,
            )
            state.cursor_last_rowids[path] = max_rowid
        except sqlite3.Error:
            logger.exception(
                "failed to read cursor cli store",
                extra={"path": str(path), "window_id": str(window_id)},
            )
            continue
        for payload in payloads:
            blob_id = payload.get("blob_id")
            if blob_id is not None:
                seen.add(str(blob_id))
            payload["client_id"] = str(client_id)
            payload["virtual_window_id"] = str(window_id)
            payload["project_path"] = project_path
            events.append(
                ManagedAiEvent(
                    provider="cursor_cli",
                    client_id=client_id,
                    window_id=window_id,
                    source_path=str(path),
                    offset=None,
                    cursor=root_blob_id,
                    project_path=project_path,
                    payload=payload,
                )
            )
    return events


def _extract_conversation_id(content: str | None) -> str | None:
    if not content:
        return None
    match = re.search(r'"conversationId"\s*:\s*"([^"]+)"', content)
    if match:
        return match.group(1).strip()
    return None


def _extract_antigravity_parent_message_sender(content: str | None) -> str | None:
    if not content:
        return None
    match = re.search(r"\[Message\]\s+.*?\bsender=(\S+)\s+", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def collect_antigravity_watch_events(
    state: AgentToolWatcherState,
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
) -> list[ManagedAiEvent]:
    # Pass 1: Read all new payloads and populate state.antigravity_subagent_targets
    all_payloads: list[tuple[Path, str, list[tuple[dict[str, Any], int]], int]] = []
    for path in _cached_antigravity_transcript_files(state, window_id):
        offset = state.antigravity_offsets.get(path, 0)
        try:
            if offset > path.stat().st_size:
                offset = 0
            payloads, next_offset = read_new_jsonl_events(path, offset)
        except FileNotFoundError:
            state.antigravity_offsets.pop(path, None)
            continue

        session_id = antigravity_session_id_from_transcript_path(path) or path.parent.parent.parent.name

        # Look for INVOKE_SUBAGENT events to populate targets
        for payload, line_offset in payloads:
            raw_type = payload.get("type")
            step_index = payload.get("step_index")
            if raw_type == "INVOKE_SUBAGENT" and isinstance(step_index, int):
                content = payload.get("content")
                subagent_id = _extract_conversation_id(content)
                if subagent_id:
                    tool_use_id = f"step-{step_index - 1}"
                    state.antigravity_subagent_targets[subagent_id] = {
                        "parent_session_id": session_id,
                        "tool_use_id": tool_use_id,
                        "agent_id": subagent_id,
                        "source_path": str(path),
                    }

        all_payloads.append((path, session_id, payloads, next_offset))

    # Pass 2: Process all payloads and build events
    events: list[ManagedAiEvent] = []
    for path, session_id, payloads, next_offset in all_payloads:
        state.antigravity_offsets[path] = next_offset

        # Check if this session is a subagent session
        is_subagent = session_id in state.antigravity_subagent_targets
        subagent_meta = state.antigravity_subagent_targets.get(session_id)

        resolved_session_id = f"agent-{session_id}" if is_subagent else session_id

        # Construct a virtual subagent source path for subagent tree linking in the frontend
        subagent_source_path = None
        if is_subagent and subagent_meta:
            subagent_source_path = f"/tmp/{subagent_meta['parent_session_id']}/subagents/agent-{session_id}.jsonl"

        for payload, line_offset in payloads:
            payload.setdefault("WEB_TERMINAL_CLIENT_ID", str(client_id))
            payload.setdefault("WEB_TERMINAL_WINDOW_ID", str(window_id))
            payload.setdefault("WEB_TERMINAL_PROJECT_PATH", project_path or "")
            payload.setdefault("session_id", resolved_session_id)
            payload.setdefault("source_path", subagent_source_path if is_subagent else str(path))
            payload.setdefault("offset", line_offset)
            payload["project_path"] = project_path

            if is_subagent and subagent_meta:
                payload.setdefault("subagent", {
                    "toolUseId": subagent_meta["tool_use_id"],
                    "tool_use_id": subagent_meta["tool_use_id"],
                    "agentId": subagent_meta["agent_id"],
                    "agent_id": subagent_meta["agent_id"],
                })
                payload.setdefault("agentId", subagent_meta["agent_id"])
                payload.setdefault("sessionId", subagent_meta["parent_session_id"])
                payload.setdefault("isSidechain", True)
            else:
                # If not a subagent, check if it's the invoke_subagent tool call to attach matches
                tool_calls = payload.get("tool_calls")
                step_index = payload.get("step_index")
                if isinstance(tool_calls, list) and isinstance(step_index, int):
                    has_invoke = any(
                        isinstance(call, dict) and call.get("name") == "invoke_subagent"
                        for call in tool_calls
                    )
                    if has_invoke:
                        tool_use_id = f"step-{step_index}"
                        # Look for target mapped to this tool call
                        matches = []
                        for sub_id, meta in state.antigravity_subagent_targets.items():
                            if meta.get("tool_use_id") == tool_use_id and meta.get("parent_session_id") == session_id:
                                matches.append({
                                    "tool_use_id": tool_use_id,
                                    "agent_id": sub_id,
                                })
                        if matches:
                            payload.setdefault("subagent_tool_use_results", matches)

                # Check if it's the tool result INVOKE_SUBAGENT
                raw_type = payload.get("type")
                if raw_type == "INVOKE_SUBAGENT" and isinstance(step_index, int):
                    tool_use_id = f"step-{step_index - 1}"
                    # Find mapped subagent ID
                    subagent_id = None
                    for sub_id, meta in state.antigravity_subagent_targets.items():
                        if meta.get("tool_use_id") == tool_use_id and meta.get("parent_session_id") == session_id:
                            subagent_id = sub_id
                            break
                    if subagent_id:
                        payload.setdefault("toolUseResult", {
                            "agentId": subagent_id,
                            "toolUseId": tool_use_id,
                        })
                elif raw_type == "SYSTEM_MESSAGE":
                    subagent_id = _extract_antigravity_parent_message_sender(payload.get("content"))
                    meta = state.antigravity_subagent_targets.get(subagent_id or "")
                    if meta and meta.get("parent_session_id") == session_id:
                        payload.setdefault("toolUseResult", {
                            "agentId": subagent_id,
                            "toolUseId": meta["tool_use_id"],
                        })

            events.append(
                ManagedAiEvent(
                    provider="antigravity_cli",
                    client_id=client_id,
                    window_id=window_id,
                    source_path=subagent_source_path if is_subagent else str(path),
                    offset=line_offset,
                    cursor=line_offset,
                    project_path=project_path,
                    payload=payload,
                )
            )

    return events


AGENT_TOOL_COLLECTORS: tuple[tuple[str, str], ...] = _agent_tool_collectors(globals())


async def watch_agent_tool_events(
    send_event: ManagedEventSender,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
    *,
    send_presence: PresenceEventSender | None = None,
    terminal: ClientTerminalMultiplexer | None = None,
    runtime: ClientTmuxRuntime | None = None,
    idle_supervisor: AgentIdleSupervisor | None = None,
    providers: frozenset[str] | set[str] | None = None,
) -> None:
    state = AgentToolWatcherState()
    provider_filter = _normalize_provider_filter(providers)
    sleep_seconds = AGENT_WATCH_IDLE_INTERVAL_SECONDS
    await _run_watcher_scan(initialize_agent_tool_watcher_state, state, window_id=window_id)
    process_scan_interval = max(PRESENCE_SEND_INTERVAL_SECONDS, AGENT_WATCH_PROCESS_SCAN_INTERVAL_SECONDS)
    next_process_scan_at = time.perf_counter() + _initial_process_scan_delay(window_id, process_scan_interval)
    while True:
        started_at = time.perf_counter()
        managed_events = await _run_watcher_scan(
            _collect_all_events,
            state,
            client_id=client_id,
            window_id=window_id,
            project_path=project_path,
            providers=provider_filter,
        )
        sent_count = 0
        if idle_supervisor is not None and managed_events:
            await idle_supervisor.observe_events(managed_events)
        for event in managed_events:
            if await enqueue_managed_ai_event(send_event, event):
                sent_count += 1
        now = time.perf_counter()
        process_scan_due = now >= next_process_scan_at
        if idle_supervisor is not None and process_scan_due:
            await idle_supervisor.maybe_suspend_window(window_id)

        if send_presence is not None and process_scan_due:
            presence = await detect_agent_work_presence(
                window_id,
                terminal=terminal,
                runtime=runtime,
            )
            if presence is not None:
                await send_presence(
                    AgentMessage(
                        type="agent_work_presence",
                        client_id=client_id,
                        window_id=window_id,
                        payload={
                            "providers": list(presence.providers),
                            "reasons": list(presence.reasons),
                        },
                    )
                )
                sent_count += 1
        if process_scan_due:
            next_process_scan_at = now + process_scan_interval

        elapsed = time.perf_counter() - started_at
        if elapsed >= AGENT_WATCH_SLOW_SCAN_SECONDS:
            logger.warning(
                "client-agent agent watcher scan was slow",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(window_id),
                    "event_count": sent_count,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )

        if sent_count:
            sleep_seconds = AGENT_WATCH_ACTIVE_INTERVAL_SECONDS
        else:
            sleep_seconds = min(
                AGENT_WATCH_MAX_INTERVAL_SECONDS,
                max(AGENT_WATCH_IDLE_INTERVAL_SECONDS, sleep_seconds * 1.5),
            )
        await asyncio.sleep(sleep_seconds)


def _watch_collection_semaphore() -> asyncio.Semaphore:
    global _WATCH_COLLECTION_SEMAPHORE, _WATCH_COLLECTION_SEMAPHORE_LOOP

    loop = asyncio.get_running_loop()
    if _WATCH_COLLECTION_SEMAPHORE is None or _WATCH_COLLECTION_SEMAPHORE_LOOP is not loop:
        _WATCH_COLLECTION_SEMAPHORE = asyncio.Semaphore(AGENT_WATCH_COLLECTION_CONCURRENCY)
        _WATCH_COLLECTION_SEMAPHORE_LOOP = loop
    return _WATCH_COLLECTION_SEMAPHORE


async def _run_watcher_scan(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    async with _watch_collection_semaphore():
        return await asyncio.to_thread(func, *args, **kwargs)


__all__ = [name for name in globals() if not name.startswith("__")]
