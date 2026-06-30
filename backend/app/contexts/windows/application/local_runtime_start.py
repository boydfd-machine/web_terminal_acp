from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from uuid import UUID

from app.models import WindowStatus
from app.contexts.windows.infrastructure.repository import get_window_for_client
from app.platform.polling_response_cache import invalidate_polling_response_cache_async
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, TmuxTarget

logger = logging.getLogger(__name__)
LOCAL_CREATE_WINDOW_TIMEOUT_SECONDS = 30.0


def schedule_local_window_runtime_start(
    *,
    client_id: UUID,
    window_id: UUID,
    cwd: str | None,
    shell_command: str | None,
    agent_ops_token: str | None = None,
    tmux_manager: TmuxManager,
    session_factory: Callable[[], object],
    ui_event_hub,
) -> None:
    task = asyncio.create_task(
        start_local_window_runtime(
            client_id=client_id,
            window_id=window_id,
            cwd=cwd,
            shell_command=shell_command,
            agent_ops_token=agent_ops_token,
            tmux_manager=tmux_manager,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    )
    task.add_done_callback(_log_local_window_runtime_start_failure)


async def start_local_window_runtime(
    *,
    client_id: UUID,
    window_id: UUID,
    cwd: str | None,
    shell_command: str | None,
    agent_ops_token: str | None,
    tmux_manager: TmuxManager,
    session_factory: Callable[[], object],
    ui_event_hub,
) -> None:
    tmux_target = None
    try:
        tmux_target = await asyncio.wait_for(
            tmux_manager.create_window(
                cwd,
                shell_command,
                client_id=client_id,
                window_id=window_id,
                agent_ops_token=agent_ops_token,
            ),
            timeout=LOCAL_CREATE_WINDOW_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        current_task = asyncio.current_task()
        if current_task is not None and current_task.cancelling():
            raise
        logger.exception(
            "local runtime was cancelled during async window start",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
        )
        await update_local_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.error,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_error",
        )
        return
    except Exception:
        logger.exception(
            "local runtime failed during async window start",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
        )
        await update_local_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.error,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_error",
        )
        return

    try:
        updated = await persist_local_runtime_window(
            session_factory,
            client_id,
            window_id,
            tmux_target,
        )
    except Exception:
        logger.exception(
            "failed to persist local runtime window",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
        )
        with contextlib.suppress(Exception):
            await tmux_manager.kill_window(tmux_target)
        await update_local_window_status(
            session_factory,
            client_id,
            window_id,
            WindowStatus.error,
            ui_event_hub=ui_event_hub,
            reason="window_runtime_error",
        )
        return
    await invalidate_polling_response_cache_async(["tree", "window"], client_id=client_id)
    if not updated:
        with contextlib.suppress(Exception):
            await tmux_manager.kill_window(tmux_target)
        return
    await _publish_runtime_ready(ui_event_hub, client_id, window_id)


async def persist_local_runtime_window(
    session_factory: Callable[[], object],
    client_id: UUID,
    window_id: UUID,
    tmux_target: TmuxTarget,
) -> bool:
    async with session_factory() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is None:
            return False
        window.tmux_session = tmux_target.session
        window.tmux_window_id = tmux_target.window_id
        window.tmux_window_index = tmux_target.window_index
        window.cwd = getattr(tmux_target, "cwd", None) or window.cwd
        window.shell_command = getattr(tmux_target, "shell_command", None) or window.shell_command
        window.status = WindowStatus.active
        await session.commit()
        return True


async def update_local_window_status(
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


def _log_local_window_runtime_start_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "local window runtime start task crashed",
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
