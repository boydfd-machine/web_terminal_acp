from app.contexts.windows.api.agent_launch_config import *  # noqa: F403
from app.contexts.windows.api.agent_record_projection import *  # noqa: F403
from app.contexts.windows.api.response_projection import *  # noqa: F403

from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.local_runtime_start import (
    persist_local_runtime_window as _persist_local_runtime_window,
)
from app.contexts.windows.application.local_runtime_start import (
    schedule_local_window_runtime_start as _schedule_local_window_runtime_start,
)
from app.contexts.windows.application.local_runtime_start import start_local_window_runtime as _start_local_window_runtime
from app.contexts.windows.application.local_runtime_start import update_local_window_status as _update_local_window_status
from app.contexts.windows.application.remote_runtime_start import (
    persist_remote_runtime_window as _persist_remote_runtime_window,
)
from app.contexts.windows.application.remote_runtime_start import (
    schedule_remote_window_runtime_start as _schedule_remote_window_runtime_start,
)
from app.contexts.windows.application.remote_runtime_start import (
    start_remote_window_runtime as _start_remote_window_runtime,
)
from app.contexts.windows.application.remote_runtime_start import (
    update_remote_window_status as _update_remote_window_status,
)
from app.contexts.windows.application.window_cloning import clone_remote_virtual_window_for_client
from app.contexts.windows.application.window_cloning import clone_virtual_window_for_client
from app.contexts.windows.application.window_creation import create_remote_virtual_window_for_client
from app.contexts.windows.application.window_creation import create_virtual_window_for_client


async def _create_virtual_window_for_client(
    client: _RuntimeClient,
    payload: WindowCreateIn,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None = None,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    ui_event_hub=None,
) -> WindowOut:
    try:
        result = await create_virtual_window_for_client(
            client,
            payload,
            session,
            tmux_manager,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


async def _create_remote_virtual_window_for_client(
    client: _RuntimeClient,
    payload: WindowCreateIn,
    session: AsyncSession,
    registry: ClientConnectionRegistry,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    ui_event_hub=None,
) -> WindowOut:
    try:
        result = await create_remote_virtual_window_for_client(
            client,
            payload,
            session,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


async def _clone_virtual_window_for_client(
    client: _RuntimeClient,
    source_window: VirtualWindow,
    payload: WindowCloneIn,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None = None,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    ui_event_hub=None,
) -> WindowOut:
    try:
        result = await clone_virtual_window_for_client(
            client,
            source_window,
            payload,
            session,
            tmux_manager,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


async def _clone_remote_virtual_window_for_client(
    client: _RuntimeClient,
    source_window: VirtualWindow,
    payload: WindowCloneIn,
    session: AsyncSession,
    registry: ClientConnectionRegistry,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    ui_event_hub=None,
) -> WindowOut:
    try:
        result = await clone_remote_virtual_window_for_client(
            client,
            source_window,
            payload,
            session,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


__all__ = [name for name in globals() if not name.startswith("__")]
