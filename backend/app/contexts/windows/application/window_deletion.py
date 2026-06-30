from __future__ import annotations

import contextlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, ClientRuntime, VirtualWindow
from app.contexts.windows.infrastructure.repository import delete_window, get_window_for_client
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError
from app.contexts.terminal_runtime.application.clone import remove_window_agent_homes
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, TmuxTarget
from app.contexts.windows.application.errors import WindowServiceError


async def delete_virtual_window_for_client(
    client: Client,
    window_id: UUID,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None = None,
) -> None:
    window = await get_window_for_client(session, client.id, window_id)
    if window is None:
        raise WindowServiceError(404, "window not found")

    await kill_runtime_window(client, window, registry, tmux_manager=tmux_manager)
    if client.runtime is ClientRuntime.local:
        remove_window_agent_homes(window_id)
    deleted = await delete_window(session, client.id, window_id)
    if not deleted:
        raise WindowServiceError(404, "window not found")
    await session.commit()


async def kill_runtime_window(
    client: Client,
    window: VirtualWindow,
    registry: ClientConnectionRegistry | None,
    *,
    tmux_manager: TmuxManager,
) -> None:
    if client.runtime is ClientRuntime.local:
        if window.tmux_session and window.tmux_window_id:
            with contextlib.suppress(Exception):
                await tmux_manager.kill_window(
                    TmuxTarget(
                        session=window.tmux_session,
                        window_id=window.tmux_window_id,
                        local_window_id=window.id,
                    )
                )
        return

    if registry is None:
        return
    if not window.remote_session_id or not window.remote_window_id:
        return
    remote_runtime = RemoteRuntime(client_id=client.id, registry=registry)
    with contextlib.suppress(RemoteClientUnavailable, RemoteTerminalError):
        await remote_runtime.kill_window(
            window_id=window.id,
            remote_session_id=window.remote_session_id,
            remote_window_id=window.remote_window_id,
        )
