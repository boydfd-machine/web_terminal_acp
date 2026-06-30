from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from uuid import UUID

from app.models import WindowStatus
from app.contexts.windows.infrastructure.repository import get_window_for_client
from app.platform.polling_response_cache import invalidate_polling_response_cache_async
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError

logger = logging.getLogger(__name__)
REMOTE_CREATE_WINDOW_TIMEOUT_SECONDS = 60.0


def schedule_remote_window_runtime_start(
    *,
    client_id: UUID,
    window_id: UUID,
    cwd: str | None,
    shell_command: str | None,
    agent_config_selection: dict[str, object] | None,
    system_config_files: dict[str, object] | None,
    agent_profile_id: str | None,
    agent_profile_agent: str | None,
    agent_model_settings: dict[str, object] | None = None,
    agent_model_agent: str | None = None,
    agent_ops_token: str | None = None,
    clone_source_window_id: UUID | str | None = None,
    registry: ClientConnectionRegistry,
    session_factory: Callable[[], object],
    ui_event_hub,
) -> None:
    task = asyncio.create_task(
        start_remote_window_runtime(
            client_id=client_id,
            window_id=window_id,
            cwd=cwd,
            shell_command=shell_command,
            agent_config_selection=agent_config_selection,
            system_config_files=system_config_files,
            agent_profile_id=agent_profile_id,
            agent_profile_agent=agent_profile_agent,
            agent_model_settings=agent_model_settings,
            agent_model_agent=agent_model_agent,
            agent_ops_token=agent_ops_token,
            clone_source_window_id=clone_source_window_id,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    )
    task.add_done_callback(_log_remote_window_runtime_start_failure)


async def start_remote_window_runtime(
    *,
    client_id: UUID,
    window_id: UUID,
    cwd: str | None,
    shell_command: str | None,
    agent_config_selection: dict[str, object] | None,
    system_config_files: dict[str, object] | None,
    agent_profile_id: str | None,
    agent_profile_agent: str | None,
    agent_model_settings: dict[str, object] | None,
    agent_model_agent: str | None,
    agent_ops_token: str | None,
    clone_source_window_id: UUID | str | None,
    registry: ClientConnectionRegistry,
    session_factory: Callable[[], object],
    ui_event_hub,
) -> None:
    remote_runtime = RemoteRuntime(
        client_id=client_id,
        registry=registry,
        request_timeout=REMOTE_CREATE_WINDOW_TIMEOUT_SECONDS,
    )
    try:
        runtime_window = await remote_runtime.create_window(
            cwd=cwd,
            shell_command=shell_command,
            window_id=window_id,
            agent_config_selection=agent_config_selection,
            system_config_files=system_config_files,
            agent_profile_id=agent_profile_id,
            agent_profile_agent=agent_profile_agent,
            agent_model_settings=agent_model_settings,
            agent_model_agent=agent_model_agent,
            agent_ops_token=agent_ops_token,
            clone_source_window_id=clone_source_window_id,
        )
    except RemoteClientUnavailable as exc:
        logger.warning(
            "remote runtime unavailable during async window start",
            extra={
                "client_id": str(client_id),
                "window_id": str(window_id),
                "reason": getattr(exc, "reason", "unknown"),
            },
        )
        await update_remote_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.disconnected,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_unavailable",
        )
        return
    except RemoteTerminalError as exc:
        logger.warning(
            "remote runtime failed during async window start",
            extra={
                "client_id": str(client_id),
                "window_id": str(window_id),
                "error": str(exc),
            },
        )
        await update_remote_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.error,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_error",
        )
        return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "remote runtime crashed during async window start",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
        )
        await update_remote_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.error,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_error",
        )
        return

    updated = await persist_remote_runtime_window(
        session_factory,
        client_id,
        window_id,
        runtime_window,
    )
    await invalidate_polling_response_cache_async(["tree", "window"], client_id=client_id)
    if not updated:
        with contextlib.suppress(RemoteClientUnavailable, RemoteTerminalError):
            await remote_runtime.kill_window(
                window_id=window_id,
                remote_session_id=runtime_window.session_id,
                remote_window_id=runtime_window.window_id,
            )
        return
    await _publish_runtime_ready(ui_event_hub, client_id, window_id)


async def persist_remote_runtime_window(
    session_factory: Callable[[], object],
    client_id: UUID,
    window_id: UUID,
    runtime_window,
) -> bool:
    async with session_factory() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is None:
            return False
        window.remote_session_id = runtime_window.session_id
        window.remote_window_id = runtime_window.window_id
        window.cwd = runtime_window.cwd
        window.shell_command = runtime_window.shell_command
        window.status = WindowStatus.active
        await session.commit()
        return True


async def update_remote_window_status(
    session_factory: Callable[[], object],
    client_id: UUID,
    window_id: UUID,
    status_value: WindowStatus,
    *,
    ui_event_hub,
    reason: str,
) -> bool:
    async with session_factory() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is None:
            return False
        window.status = status_value
        await session.commit()
    await invalidate_polling_response_cache_async(["tree", "window"], client_id=client_id)
    if ui_event_hub is not None:
        with contextlib.suppress(Exception):
            await ui_event_hub.publish_invalidation(
                ["tree", "window"],
                client_id=client_id,
                window_id=window_id,
                reason=reason,
            )
    return True


def _log_remote_window_runtime_start_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "remote window runtime start task crashed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


async def _publish_runtime_ready(ui_event_hub, client_id: UUID, window_id: UUID) -> None:
    if ui_event_hub is None:
        return
    with contextlib.suppress(Exception):
        await ui_event_hub.publish_invalidation(
            ["tree", "window"],
            client_id=client_id,
            window_id=window_id,
            reason="window_runtime_ready",
        )
