# ruff: noqa: F401,F403,F405

import asyncio
import contextlib
import logging
import re
import tempfile
import time
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.plugins.artifact_plugins import get_artifact_plugin_registry_for_scope
from app.platform.plugins.artifact_plugins.user_settings_repository import (
    restore_artifact_plugin_files_to_disk,
)
from app.client_agent.agent_commands import agent_provider_from_command
from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    Event,
    TerminalArtifact,
    VirtualWindow,
    WindowStatus,
)
from app.contexts.terminal_artifacts.infrastructure.repository import (
    get_terminal_artifact_for_client, mark_artifact_failed, mark_artifact_running, mark_artifact_succeeded,
)
from app.contexts.windows.application.window_lookup import create_window, delete_window, get_window_for_client
from app.platform.polling_response_cache import invalidate_polling_response_cache_async
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.application.runtime_provider import RemoteRuntime, RemoteTerminalError
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.application.clone import clone_resume_command, clone_window_agent_homes, remove_window_agent_homes
from app.contexts.terminal_artifacts.application.artifact_completion import (
    complete_project_todos_after_artifact_status_change,
)
from app.contexts.terminal_artifacts.application.generation_request import TerminalArtifactGenerationRequest
from app.contexts.terminal_artifacts.application.model_selection import (
    artifact_model_selection_for_generation,
)
from app.contexts.terminal_artifacts.application.prompt_language import _artifact_prompt_with_output_language
import app.contexts.terminal_artifacts.application.project_incremental as project_artifacts
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager

logger = logging.getLogger(__name__)

ARTIFACT_OUTPUT_IDLE_GRACE_SECONDS = 5.0
ARTIFACT_AGENT_READY_TIMEOUT_SECONDS = 120.0
ARTIFACT_AGENT_READY_SETTLE_SECONDS = 0.2
ARTIFACT_AGENT_READY_CAPTURE_INTERVAL_SECONDS = 0.5
ARTIFACT_OUTPUT_MAX_BYTES = 2 * 1024 * 1024
ARTIFACT_OUTPUT_FILE_MAX_BYTES = 2 * 1024 * 1024
ARTIFACT_OUTPUT_FILE_POLL_INTERVAL_SECONDS = 0.5
ARTIFACT_REMOTE_RUNTIME_REQUEST_TIMEOUT_SECONDS = 5.0
ARTIFACT_CAPTURE_HISTORY_LINES = 5000
ARTIFACT_CODEX_COMPOSER_SUBMIT_INPUT = b"\x1b[13u"
ARTIFACT_CODEX_FOLLOWUP_SUBMIT_INTERVAL_SECONDS = 0.5
ARTIFACT_CODEX_FOLLOWUP_SUBMIT_DURATION_SECONDS = 10.0
ARTIFACT_TERMINAL_RETENTION_METADATA_KEY = "terminal_retention_seconds"
ARTIFACT_TERMINAL_RETENTION_MAX_SECONDS = 3600.0
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def schedule_terminal_artifact_generation(
    request: TerminalArtifactGenerationRequest,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    tmux_manager: TmuxManager | None = None,
    terminal_broker: TerminalBroker | None = None,
    registry: ClientConnectionRegistry | None = None,
    ui_event_hub=None,
    plugin_registry=None,
) -> asyncio.Task[None]:
    task = asyncio.create_task(
        generate_terminal_artifact(
            request,
            session_factory=session_factory,
            tmux_manager=tmux_manager or get_tmux_manager(),
            terminal_broker=terminal_broker,
            registry=registry,
            ui_event_hub=ui_event_hub,
            plugin_registry=plugin_registry,
        )
    )
    task.add_done_callback(_log_terminal_artifact_task_failure)
    return task


def _log_terminal_artifact_task_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "terminal artifact generation task crashed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


async def generate_terminal_artifact(
    request: TerminalArtifactGenerationRequest,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    ui_event_hub=None,
    plugin_registry=None,
) -> None:
    ephemeral_window_id: UUID | None = None
    ephemeral_runtime_window: RuntimeWindow | None = None
    terminal_retention_seconds: float | None = None
    retain_terminal_before_cleanup = True
    try:
        async with session_factory() as session:
            client, source_window, artifact = await _load_generation_state(session, request)
            terminal_retention_seconds = _artifact_terminal_retention_seconds(artifact.metadata_json)
            await restore_artifact_plugin_files_to_disk(
                session,
                owner_user_id=client.owner_user_id,
            )
            plugins = plugin_registry or get_artifact_plugin_registry_for_scope(
                artifact.artifact_scope,
                owner_user_id=client.owner_user_id,
            )
            plugin = plugins.by_kind(artifact.artifact_kind)
            project_workspace = await project_artifacts.project_artifact_workspace_for(session, artifact, plugin)
            source_agent_command = await _resolve_source_agent_command(session, source_window)
            artifact_model_agent, artifact_model_settings = await artifact_model_selection_for_generation(
                session,
                source_window,
                artifact,
                source_agent_command=source_agent_command,
            )
            ephemeral_window = await _create_ephemeral_window(
                session,
                client,
                source_window,
                artifact,
                source_agent_command=source_agent_command,
                artifact_model_agent=artifact_model_agent,
                artifact_model_settings=artifact_model_settings,
                tmux_manager=tmux_manager,
                registry=registry,
            )
            ephemeral_window_id = ephemeral_window.id
            ephemeral_runtime_window = _runtime_window_for_ephemeral(ephemeral_window)
            await mark_artifact_running(
                session,
                artifact,
                ephemeral_window_id=ephemeral_window_id,
            )
            await session.commit()
            await _publish_artifact_invalidation(ui_event_hub, artifact, reason="artifact_running")

        runtime_window = ephemeral_runtime_window
        output_path = project_workspace.output_path if project_workspace else _artifact_output_path(request.artifact_id)
        artifact_prompt = plugin.build_prompt(
            source_title=source_window.title,
            user_prompt=request.prompt,
            output_path=output_path,
        )
        if project_workspace is not None:
            artifact_prompt += project_workspace.prompt_instructions
        output = await _run_artifact_prompt(
            client,
            source_window,
            ephemeral_window,
            runtime_window,
            _artifact_prompt_with_output_language(
                artifact_prompt,
                request.output_language or get_settings().summary_output_language,
            ),
            output_path=output_path,
            source_agent_command=source_agent_command,
            is_complete=lambda value: _plugin_output_is_complete(plugin, value),
            session_factory=session_factory,
            terminal_broker=terminal_broker,
            tmux_manager=tmux_manager,
            registry=registry,
            before_send=(
                (lambda broker: project_artifacts.write_project_artifact_workspace(broker, client.id, project_workspace))
                if project_workspace is not None
                else None
            ),
        )
        content_json = plugin.parse_output(output)
        rendered = plugin.render(content_json)

        async with session_factory() as session:
            artifact = await get_terminal_artifact_for_client(
                session,
                request.client_id,
                request.window_id,
                request.artifact_id,
            )
            if artifact is not None:
                await mark_artifact_succeeded(
                    session,
                    artifact,
                    content_json=rendered.content_json,
                    display_html=rendered.display_html,
                    metadata_json={**(artifact.metadata_json or {}), **rendered.metadata_json},
                )
                await complete_project_todos_after_artifact_status_change(session, artifact.id)
                await session.commit()
                await _publish_artifact_invalidation(ui_event_hub, artifact, reason="artifact_succeeded")
    except asyncio.CancelledError:
        retain_terminal_before_cleanup = False
        raise
    except Exception as exc:
        await _mark_generation_failed(
            request,
            error=str(exc),
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    finally:
        if ephemeral_window_id is not None:
            cleanup_cancelled = False
            try:
                if retain_terminal_before_cleanup:
                    await _wait_before_ephemeral_window_cleanup(terminal_retention_seconds)
            except asyncio.CancelledError:
                cleanup_cancelled = True
            finally:
                await _cleanup_ephemeral_window(
                    request.client_id,
                    ephemeral_window_id,
                    session_factory=session_factory,
                    tmux_manager=tmux_manager,
                    registry=registry,
                    runtime_window=ephemeral_runtime_window,
                )
                await _publish_artifact_terminal_cleanup_invalidation(
                    ui_event_hub,
                    request.client_id,
                    request.window_id,
                )
            if cleanup_cancelled:
                raise asyncio.CancelledError


async def _load_generation_state(
    session: AsyncSession,
    request: TerminalArtifactGenerationRequest,
) -> tuple[Client, VirtualWindow, TerminalArtifact]:
    client = await session.get(Client, request.client_id)
    if client is None:
        raise ValueError("client not found")
    source_window = await get_window_for_client(session, request.client_id, request.window_id)
    if source_window is None:
        raise ValueError("window not found")
    artifact = await get_terminal_artifact_for_client(
        session,
        request.client_id,
        request.window_id,
        request.artifact_id,
    )
    if artifact is None:
        raise ValueError("artifact not found")
    return client, source_window, artifact


async def _resolve_source_agent_command(
    session: AsyncSession,
    source_window: VirtualWindow,
) -> str | None:
    if source_window.shell_command and _looks_like_agent_command(source_window.shell_command):
        return source_window.shell_command

    latest_command = await session.scalar(
        select(Event.payload_json)
        .where(
            Event.client_id == source_window.client_id,
            Event.virtual_window_id == source_window.id,
            Event.kind == "terminal_input_command",
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
    )
    if isinstance(latest_command, dict):
        command = latest_command.get("command")
        if isinstance(command, str) and _looks_like_agent_command(command):
            return command

    latest_ai_session = await session.scalar(
        select(AiSession)
        .where(
            AiSession.client_id == source_window.client_id,
            AiSession.virtual_window_id == source_window.id,
        )
        .order_by(desc(AiSession.updated_at), desc(AiSession.created_at), desc(AiSession.id))
        .limit(1)
    )
    if latest_ai_session is None or not latest_ai_session.provider:
        return None
    try:
        return get_agent_plugin_registry().by_provider(latest_ai_session.provider).command.default_command
    except ValueError:
        return None


async def _create_ephemeral_window(
    session: AsyncSession,
    client: Client,
    source_window: VirtualWindow,
    artifact: TerminalArtifact | None,
    *,
    source_agent_command: str | None = None,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    window_title: str | None = None,
    derived_context_extras: dict | None = None,
    artifact_model_agent: str | None = None,
    artifact_model_settings=None,
) -> VirtualWindow:
    window_id = uuid4()
    clone_result = SimpleNamespace(cloned_agents=(), session_ids={}, resume_commands={})
    runtime_window: RuntimeWindow | None = None
    try:
        if client.runtime is ClientRuntime.local:
            clone_result = clone_window_agent_homes(
                source_window.id,
                window_id,
                source_cwd=source_window.cwd,
                isolate_sessions=True,
            )
            source_shell_command = source_agent_command or source_window.shell_command
            cloned_shell_command = (
                clone_resume_command(source_shell_command, clone_result)
                or source_shell_command
            )
            if artifact_model_agent is not None:
                from app.contexts.agent_profiles.application import config_selection as agent_config_service

                agent_config_service.materialize_agent_model_settings_for_window(
                    artifact_model_agent,
                    artifact_model_settings,
                    window_id=str(window_id),
                )
            target = await tmux_manager.create_window(
                source_window.cwd,
                cloned_shell_command,
                client_id=client.id,
                window_id=window_id,
            )
            runtime_window = RuntimeWindow(
                session_id=target.session,
                window_id=target.window_id,
                window_index=getattr(target, "window_index", None),
                cwd=target.cwd,
                shell_command=target.shell_command,
            )
        else:
            if registry is None:
                raise ValueError("remote runtime unavailable")
            remote_runtime = RemoteRuntime(client_id=client.id, registry=registry, request_timeout=30.0)
            runtime_window = await remote_runtime.create_window(
                cwd=source_window.cwd,
                shell_command=source_agent_command or source_window.shell_command,
                window_id=window_id,
                clone_source_window_id=source_window.id,
                isolate_clone_sessions=True,
                agent_model_agent=artifact_model_agent,
                agent_model_settings=_artifact_model_settings_payload(artifact_model_settings),
            )

        derived_context: dict = {
            "source_window_id": str(source_window.id),
            "source_agent_command": source_agent_command,
            "cloned_agents": list(clone_result.cloned_agents),
            "session_ids": clone_result.session_ids,
            "resume_commands": clone_result.resume_commands,
        }
        if artifact is not None:
            derived_context["artifact_id"] = str(artifact.id)
            derived_context["artifact_kind"] = artifact.artifact_kind
        artifact_model_context = _artifact_model_settings_safe_payload(artifact_model_settings)
        if artifact_model_context is not None:
            derived_context["agent_model"] = artifact_model_context
        if derived_context_extras:
            derived_context.update(derived_context_extras)
        window = await create_window(
            session,
            client.id,
            cwd=runtime_window.cwd,
            shell_command=runtime_window.shell_command,
            window_id=window_id,
            tmux_session=runtime_window.session_id if client.runtime is ClientRuntime.local else None,
            tmux_window_id=runtime_window.window_id if client.runtime is ClientRuntime.local else None,
            tmux_window_index=runtime_window.window_index if client.runtime is ClientRuntime.local else None,
            remote_session_id=runtime_window.session_id if client.runtime is not ClientRuntime.local else None,
            remote_window_id=runtime_window.window_id if client.runtime is not ClientRuntime.local else None,
            folder_id=source_window.folder_id,
            title=window_title or f"{source_window.title} artifact",
            parent_window_id=source_window.id,
            root_window_id=source_window.root_window_id or source_window.id,
            derived_mode="ephemeral",
            derived_context=derived_context,
        )
        window.status = WindowStatus.active
        return window
    except Exception:
        if runtime_window is not None:
            await _kill_runtime_window(client, window_id, runtime_window, tmux_manager, registry)
        elif client.runtime is not ClientRuntime.local:
            await _kill_remote_runtime_window_by_local_id(client, window_id, registry)
        remove_window_agent_homes(window_id)
        raise


def _artifact_model_settings_payload(settings) -> dict[str, object] | None:
    if settings is None:
        return None
    from app.contexts.agent_profiles.application import config_selection as agent_config_service

    return agent_config_service.resolved_agent_model_settings_payload(settings)


def _artifact_model_settings_safe_payload(settings) -> dict[str, object] | None:
    if settings is None:
        return None
    from app.contexts.agent_profiles.application import config_selection as agent_config_service

    return agent_config_service.safe_agent_model_settings_payload(settings)


def _runtime_window_for_ephemeral(window: VirtualWindow) -> RuntimeWindow:
    if window.tmux_session and window.tmux_window_id:
        return RuntimeWindow(
            session_id=window.tmux_session,
            window_id=window.tmux_window_id,
            window_index=window.tmux_window_index,
            cwd=window.cwd,
            shell_command=window.shell_command,
        )
    if window.remote_session_id and window.remote_window_id:
        return RuntimeWindow(
            session_id=window.remote_session_id,
            window_id=window.remote_window_id,
            cwd=window.cwd,
            shell_command=window.shell_command,
        )
    raise ValueError("ephemeral window runtime is not ready")


async def _run_artifact_prompt(
    client: Client,
    source_window: VirtualWindow,
    ephemeral_window: VirtualWindow,
    runtime_window: RuntimeWindow,
    prompt: str,
    *,
    output_path: str | None = None,
    source_agent_command: str | None = None,
    is_complete: Callable[[str], bool],
    session_factory: Callable[[], object],
    terminal_broker: TerminalBroker | None,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    before_send: Callable[[TerminalBroker], Awaitable[None]] | None = None,
    timeout_seconds: float | None = None,
) -> str:
    broker = terminal_broker or TerminalBroker()
    if client.runtime is ClientRuntime.local:
        if broker.runtime_for(client.id) is None:
            broker.register_runtime(
                client.id,
                create_local_terminal_runtime(tmux_manager, session_factory=session_factory),
            )
    else:
        if registry is None:
            raise ValueError("remote runtime unavailable")
        broker.register_runtime(
            client.id,
            RemoteRuntime(
                client_id=client.id,
                registry=registry,
                request_timeout=ARTIFACT_REMOTE_RUNTIME_REQUEST_TIMEOUT_SECONDS,
            ),
        )

    if before_send is not None:
        await before_send(broker)

    collector = _ArtifactOutputCollector()

    async def capture_output() -> bytes:
        return await broker.capture_output_bytes(
            client.id,
            ephemeral_window.id,
            runtime_window,
            history_lines=ARTIFACT_CAPTURE_HISTORY_LINES,
        )

    shell_command = (
        source_agent_command
        or getattr(runtime_window, "shell_command", None)
        or getattr(ephemeral_window, "shell_command", None)
        or source_window.shell_command
    )
    await _wait_for_agent_terminal_ready(
        shell_command,
        collector,
        capture_output=capture_output,
    )
    await broker.send_input_direct(
        client.id,
        ephemeral_window.id,
        runtime_window,
        _command_bytes_for_prompt(shell_command, prompt),
    )
    followup_task = _schedule_artifact_followup_submits(
        broker,
        client.id,
        ephemeral_window.id,
        runtime_window,
        _followup_submit_bytes_for_prompt(shell_command),
    )
    effective_timeout = timeout_seconds or get_settings().terminal_artifact_generation_timeout_seconds
    try:
        if output_path:
            return await _read_artifact_output_file(
                broker,
                client.id,
                output_path,
                is_complete=is_complete,
                timeout_seconds=effective_timeout,
            )
        return await collector.wait_for_match(
            is_complete,
            timeout_seconds=effective_timeout,
            idle_seconds=ARTIFACT_OUTPUT_IDLE_GRACE_SECONDS,
            poll_output=capture_output,
            poll_interval_seconds=ARTIFACT_AGENT_READY_CAPTURE_INTERVAL_SECONDS,
        )
    finally:
        if followup_task is not None and not followup_task.done():
            followup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await followup_task
__all__ = [name for name in globals() if not name.startswith("__")]
