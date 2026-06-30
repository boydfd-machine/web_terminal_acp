from __future__ import annotations
# ruff: noqa: F403,F405
from app.contexts.terminal_artifacts.application.generation_service import *
from app.contexts.terminal_runtime.application.agent_prompt_input import (
    ARTIFACT_PROMPT_BRACKETED_PASTE_PROVIDERS,
    agent_prompt_followup_submit_bytes,
    command_bytes_for_agent_prompt,
    agent_provider_for_prompt,
)
from app.contexts.workspace.application.project_todo_prompt_readiness import (
    agent_terminal_is_ready as _shared_agent_terminal_is_ready,
)
def _command_bytes_for_prompt(shell_command: str | None, prompt: str) -> bytes:
    # Interactive agent commands are already running in the cloned terminal.
    return command_bytes_for_agent_prompt(
        shell_command,
        prompt,
        bracketed_paste_for_submit_providers=ARTIFACT_PROMPT_BRACKETED_PASTE_PROVIDERS,
        error_message="artifact generation requires an interactive agent terminal",
    )


def _followup_submit_bytes_for_prompt(shell_command: str | None) -> bytes | None:
    return agent_prompt_followup_submit_bytes(shell_command)


def _agent_provider_for_prompt(shell_command: str | None) -> str | None:
    return agent_provider_for_prompt(shell_command)


def _schedule_artifact_followup_submits(
    broker: TerminalBroker,
    client_id: UUID,
    window_id: UUID,
    runtime_window: RuntimeWindow,
    data: bytes | None,
) -> asyncio.Task[None] | None:
    if not data:
        return None
    task = asyncio.create_task(
        _send_artifact_followup_submits(
            broker,
            client_id,
            window_id,
            runtime_window,
            data,
            interval_seconds=ARTIFACT_CODEX_FOLLOWUP_SUBMIT_INTERVAL_SECONDS,
            duration_seconds=ARTIFACT_CODEX_FOLLOWUP_SUBMIT_DURATION_SECONDS,
        )
    )
    task.add_done_callback(_log_artifact_followup_submit_failure)
    return task


def _log_artifact_followup_submit_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.debug(
            "terminal artifact follow-up submit failed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


async def _send_artifact_followup_submits(
    broker: TerminalBroker,
    client_id: UUID,
    window_id: UUID,
    runtime_window: RuntimeWindow,
    data: bytes,
    *,
    interval_seconds: float,
    duration_seconds: float,
) -> None:
    if interval_seconds <= 0 or duration_seconds <= 0:
        return
    attempts = max(1, int(duration_seconds / interval_seconds))
    for _ in range(attempts):
        await asyncio.sleep(interval_seconds)
        await broker.send_input_direct(client_id, window_id, runtime_window, data)


def _artifact_output_path(artifact_id: UUID) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(artifact_id))
    return f"{tempfile.gettempdir()}/web-terminal-artifact-{safe_id}.json"


async def _read_artifact_output_file(
    broker: TerminalBroker,
    client_id: UUID,
    output_path: str,
    *,
    is_complete: Callable[[str], bool],
    timeout_seconds: float,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_text = ""
    while True:
        try:
            data = await broker.read_file_bytes(
                client_id,
                output_path,
                max_bytes=ARTIFACT_OUTPUT_FILE_MAX_BYTES,
            )
        except (FileNotFoundError, OSError) as exc:
            if not _looks_like_missing_artifact_file_error(exc):
                raise
            data = b""
        except RemoteTerminalError as exc:
            if not _looks_like_missing_artifact_file_error(exc):
                raise
            data = b""
        if data:
            last_text = data.decode("utf-8", errors="replace")
            if len(data) > ARTIFACT_OUTPUT_FILE_MAX_BYTES:
                raise ValueError("terminal artifact output file is too large")
            if is_complete(last_text):
                return last_text
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            detail = (
                "terminal artifact output file was incomplete"
                if last_text
                else "terminal artifact output file was not written"
            )
            raise TimeoutError(f"{detail} within {timeout_seconds:g} seconds: {output_path}")
        await asyncio.sleep(min(remaining, ARTIFACT_OUTPUT_FILE_POLL_INTERVAL_SECONDS))


def _looks_like_missing_artifact_file_error(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    text = str(exc).lower()
    return "no such file" in text or "not found" in text


def _looks_like_agent_command(shell_command: str) -> bool:
    if agent_provider_from_command(shell_command) is not None:
        return True
    lowered = shell_command.lower()
    return any(token in lowered for token in ("codex", "claude", "agent", "cursor", "agy"))


async def _wait_for_agent_terminal_ready(
    shell_command: str | None,
    collector: "_ArtifactOutputCollector",
    *,
    capture_output: Callable[[], Awaitable[bytes]] | None = None,
) -> None:
    if not shell_command or not _looks_like_agent_command(shell_command):
        return
    provider = agent_provider_from_command(shell_command)
    try:
        await _wait_until_agent_ready(provider, collector, capture_output=capture_output)
    except TimeoutError as exc:
        raise TimeoutError(
            "terminal artifact generation waited for the agent-client to become ready, "
            "but no interactive prompt was detected"
        ) from exc
    await asyncio.sleep(ARTIFACT_AGENT_READY_SETTLE_SECONDS)


async def _wait_until_agent_ready(
    provider: str | None,
    collector: "_ArtifactOutputCollector",
    *,
    capture_output: Callable[[], Awaitable[bytes]] | None,
) -> None:
    deadline = time.monotonic() + ARTIFACT_AGENT_READY_TIMEOUT_SECONDS
    last_capture_at = 0.0
    while True:
        if _agent_terminal_is_ready(provider, collector.text()):
            return

        now = time.monotonic()
        if (
            capture_output is not None
            and now - last_capture_at >= ARTIFACT_AGENT_READY_CAPTURE_INTERVAL_SECONDS
        ):
            last_capture_at = now
            await _feed_ready_capture(collector, capture_output)
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"terminal output did not match within {ARTIFACT_AGENT_READY_TIMEOUT_SECONDS:g} seconds"
            )
        wait_seconds = min(remaining, ARTIFACT_AGENT_READY_CAPTURE_INTERVAL_SECONDS)
        if capture_output is not None and last_capture_at:
            wait_seconds = min(
                wait_seconds,
                max(
                    0.01,
                    ARTIFACT_AGENT_READY_CAPTURE_INTERVAL_SECONDS - (time.monotonic() - last_capture_at),
                ),
            )
        await collector.wait_for_update(wait_seconds)


async def _feed_ready_capture(
    collector: "_ArtifactOutputCollector",
    capture_output: Callable[[], Awaitable[bytes]],
) -> None:
    try:
        snapshot = await capture_output()
    except Exception:
        logger.debug("terminal artifact readiness capture failed", exc_info=True)
        return
    if snapshot:
        await collector.feed_snapshot(snapshot)


def _agent_terminal_is_ready(provider: str | None, output: str) -> bool:
    return _shared_agent_terminal_is_ready(provider, output)


def _normalize_terminal_text(output: str) -> str:
    return _ANSI_ESCAPE.sub("", output).replace("\r", "\n")


def _codex_terminal_is_ready(text: str) -> bool:
    return (
        ("OpenAI Codex" in text or ">_ Codex" in text)
        and _terminal_has_prompt_marker(text, ("›",))
    )


def _claude_terminal_is_ready(text: str) -> bool:
    return "Claude Code" in text and _terminal_has_prompt_marker(text, ("❯",))


def _cursor_terminal_is_ready(text: str) -> bool:
    return (
        any(label in text for label in ("Cursor Agent", "Cursor CLI", "cursor-agent"))
        and _terminal_has_prompt_marker(text, (">", "›", "❯", "`"))
    )


def _antigravity_terminal_is_ready(text: str) -> bool:
    return (
        "Antigravity" in text
        and _terminal_has_prompt_marker(text, (">", "›", "❯"))
    )


def _generic_agent_terminal_is_ready(text: str) -> bool:
    return _terminal_has_prompt_marker(text, ("›", "❯", ">"))


def _terminal_has_prompt_marker(text: str, markers: tuple[str, ...]) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if any(_line_has_prompt_marker(stripped, marker) for marker in markers):
            return True
    return False


def _line_has_prompt_marker(line: str, marker: str) -> bool:
    if line == marker:
        return True
    if not line.startswith(marker):
        return False
    remainder = line[len(marker):]
    return bool(remainder) and remainder[0].isspace()


class _ArtifactOutputCollector:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._updated = asyncio.Event()
        self._last_update = time.monotonic()

    async def feed(self, data: bytes) -> None:
        if not data:
            return
        self._buffer.extend(data)
        if len(self._buffer) > ARTIFACT_OUTPUT_MAX_BYTES:
            del self._buffer[: len(self._buffer) - ARTIFACT_OUTPUT_MAX_BYTES]
        self._last_update = time.monotonic()
        self._updated.set()

    async def feed_snapshot(self, data: bytes) -> None:
        if not data or self._buffer.endswith(data):
            return
        await self.feed(data)

    async def wait_for_match(
        self,
        predicate: Callable[[str], bool],
        *,
        timeout_seconds: float,
        idle_seconds: float,
        poll_output: Callable[[], Awaitable[bytes]] | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> str:
        deadline = time.monotonic() + timeout_seconds
        matched_at: float | None = None
        last_poll_at = 0.0
        while True:
            now = time.monotonic()
            if poll_output is not None and now - last_poll_at >= poll_interval_seconds:
                last_poll_at = now
                await _feed_ready_capture(self, poll_output)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"terminal artifact generation timed out after {timeout_seconds:g} seconds")
            if self._buffer and predicate(self.text()):
                matched_at = matched_at or time.monotonic()
            else:
                matched_at = None
            if matched_at is not None and time.monotonic() - self._last_update >= idle_seconds:
                return self.text()
            self._updated.clear()
            wait_seconds = min(remaining, poll_interval_seconds if poll_output is not None else 1.0)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._updated.wait(), timeout=wait_seconds)

    async def wait_until(
        self,
        predicate: Callable[[str], bool],
        *,
        timeout_seconds: float,
    ) -> str:
        deadline = time.monotonic() + timeout_seconds
        while True:
            if predicate(self.text()):
                return self.text()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"terminal output did not match within {timeout_seconds:g} seconds")
            self._updated.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._updated.wait(), timeout=min(remaining, 1.0))

    async def wait_for_update(self, timeout_seconds: float) -> None:
        self._updated.clear()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._updated.wait(), timeout=timeout_seconds)

    def text(self) -> str:
        return self._buffer.decode("utf-8", errors="replace")


def _plugin_output_is_complete(plugin, output: str) -> bool:
    try:
        plugin.parse_output(output)
    except Exception:
        return False
    return True


async def _mark_generation_failed(
    request: TerminalArtifactGenerationRequest,
    *,
    error: str,
    session_factory: Callable[[], object],
    ui_event_hub,
) -> None:
    async with session_factory() as session:
        artifact = await get_terminal_artifact_for_client(
            session,
            request.client_id,
            request.window_id,
            request.artifact_id,
        )
        if artifact is None:
            return
        await mark_artifact_failed(session, artifact, error=error[:4000])
        await complete_project_todos_after_artifact_status_change(session, artifact.id)
        await session.commit()
        await _publish_artifact_invalidation(ui_event_hub, artifact, reason="artifact_failed")


def _artifact_terminal_retention_seconds(metadata_json: dict | None) -> float:
    if isinstance(metadata_json, dict):
        value = metadata_json.get(ARTIFACT_TERMINAL_RETENTION_METADATA_KEY)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return min(float(value), ARTIFACT_TERMINAL_RETENTION_MAX_SECONDS)
    return get_settings().terminal_artifact_terminal_retention_seconds


async def _wait_before_ephemeral_window_cleanup(retention_seconds: float | None) -> None:
    if retention_seconds is None:
        retention_seconds = get_settings().terminal_artifact_terminal_retention_seconds
    if retention_seconds <= 0:
        return
    await asyncio.sleep(retention_seconds)


async def _cleanup_ephemeral_window(
    client_id: UUID,
    ephemeral_window_id: UUID,
    *,
    session_factory: Callable[[], object],
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    runtime_window: RuntimeWindow | None = None,
) -> None:
    async with session_factory() as session:
        client = await session.get(Client, client_id)
        window = await get_window_for_client(session, client_id, ephemeral_window_id)
        if client is None:
            remove_window_agent_homes(ephemeral_window_id)
            return
        cleanup_runtime_window = _runtime_window_for_ephemeral(window) if window is not None else runtime_window
        if cleanup_runtime_window is not None:
            await _kill_runtime_window(
                client,
                ephemeral_window_id,
                cleanup_runtime_window,
                tmux_manager,
                registry,
            )
        elif client.runtime is not ClientRuntime.local:
            await _kill_remote_runtime_window_by_local_id(client, ephemeral_window_id, registry)
        if window is not None:
            await delete_window(session, client_id, ephemeral_window_id)
            await session.commit()
    remove_window_agent_homes(ephemeral_window_id)


async def _kill_runtime_window(
    client: Client,
    window_id: UUID,
    runtime_window: RuntimeWindow,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
) -> None:
    if client.runtime is ClientRuntime.local:
        from app.contexts.terminal_runtime.application.runtime_provider import TmuxTarget

        with contextlib.suppress(Exception):
            await tmux_manager.kill_window(
                TmuxTarget(
                    session=runtime_window.session_id,
                    window_id=runtime_window.window_id,
                    local_window_id=window_id,
                )
            )
        return
    if registry is None:
        return
    remote_runtime = RemoteRuntime(client_id=client.id, registry=registry, request_timeout=10.0)
    with contextlib.suppress(Exception):
        await remote_runtime.kill_window(
            window_id=window_id,
            remote_session_id=runtime_window.session_id,
            remote_window_id=runtime_window.window_id,
        )


async def _kill_remote_runtime_window_by_local_id(
    client: Client,
    window_id: UUID,
    registry: ClientConnectionRegistry | None,
) -> None:
    if registry is None:
        return
    remote_runtime = RemoteRuntime(client_id=client.id, registry=registry, request_timeout=10.0)
    with contextlib.suppress(Exception):
        await remote_runtime.kill_window(window_id=window_id)


async def _publish_artifact_invalidation(ui_event_hub, artifact: TerminalArtifact, *, reason: str) -> None:
    await invalidate_polling_response_cache_async(
        ["terminal_artifacts", "project_todos"],
        client_id=artifact.client_id,
    )
    if ui_event_hub is None:
        return
    resources = ["terminal_artifacts", "project_todos"]
    if reason == "artifact_running":
        resources.append("window")
    with contextlib.suppress(Exception):
        await ui_event_hub.publish_invalidation(
            resources,
            client_id=artifact.client_id,
            window_id=artifact.virtual_window_id,
            reason=reason,
        )


async def _publish_artifact_terminal_cleanup_invalidation(
    ui_event_hub,
    client_id: UUID,
    window_id: UUID,
) -> None:
    await invalidate_polling_response_cache_async(["terminal_artifacts"], client_id=client_id)
    if ui_event_hub is None:
        return
    with contextlib.suppress(Exception):
        await ui_event_hub.publish_invalidation(
            ["terminal_artifacts"],
            client_id=client_id,
            window_id=window_id,
            reason="artifact_terminal_cleanup",
        )
