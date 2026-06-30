from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth_enabled, create_agent_ops_token
from app.config import get_settings
from app.contexts.windows.domain.clone_spec import CloneReservation, WindowCloneSpec
from app.contexts.windows.domain.runtime_client import RuntimeClient, RuntimeClientKind
from app.models import VirtualWindow
from app.contexts.windows.infrastructure.repository import create_window
from app.contexts.windows.api.schemas import WindowCloneIn
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.clone import (
    clone_resume_command,
    clone_window_agent_homes,
    remove_window_agent_homes,
)
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.activity.application.window_runtime_tags import agent_from_command, runtime_tags_for_window
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.local_runtime_start import schedule_local_window_runtime_start
from app.contexts.windows.application.remote_runtime_start import schedule_remote_window_runtime_start
from app.contexts.windows.application.results import WindowMutationResult
from app.contexts.windows.application.clone_spec import clone_source_from_model


async def clone_virtual_window_for_client(
    client: RuntimeClient,
    source_window: VirtualWindow,
    payload: WindowCloneIn,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None = None,
    *,
    session_factory: Callable[[], object],
    ui_event_hub=None,
) -> WindowMutationResult:
    runtime = RuntimeClientKind(getattr(client.runtime, "value", client.runtime))
    if runtime is not RuntimeClientKind.local:
        if registry is None:
            raise WindowServiceError(503, "remote runtime unavailable")
        return await clone_remote_virtual_window_for_client(
            client,
            source_window,
            payload,
            session,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    return await clone_local_virtual_window_for_client(
        client,
        source_window,
        payload,
        session,
        tmux_manager,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )


async def clone_remote_virtual_window_for_client(
    client: RuntimeClient,
    source_window: VirtualWindow,
    payload: WindowCloneIn,
    session: AsyncSession,
    registry: ClientConnectionRegistry,
    *,
    session_factory: Callable[[], object],
    ui_event_hub=None,
) -> WindowMutationResult:
    _require_linked_clone(payload)
    client_id = client.id
    connection = registry.get(client_id)
    if connection is None or getattr(connection, "closed", False):
        raise WindowServiceError(503, "remote runtime unavailable")

    spec = WindowCloneSpec.remote(clone_source_from_model(source_window), payload)
    try:
        window = await _create_window_from_clone_spec(session, client_id, spec)
        await session.commit()
        await session.refresh(window)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await session.rollback()
        raise
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()
        raise

    source_token = _source_ops_token_for_window(client_id, window.id)
    schedule_remote_window_runtime_start(
        client_id=client_id,
        window_id=window.id,
        cwd=window.cwd,
        shell_command=window.shell_command,
        agent_config_selection=None,
        system_config_files=None,
        agent_profile_id=None,
        agent_profile_agent=None,
        agent_ops_token=source_token,
        clone_source_window_id=source_window.id,
        registry=registry,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )
    return WindowMutationResult(
        window=window,
        runtime_tags=runtime_tags_for_window(window, terminal_agent=agent_from_command(window.shell_command)),
    )


async def clone_local_virtual_window_for_client(
    client: RuntimeClient,
    source_window: VirtualWindow,
    payload: WindowCloneIn,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    *,
    session_factory: Callable[[], object],
    ui_event_hub=None,
) -> WindowMutationResult:
    _require_linked_clone(payload)
    window_id = uuid4()
    try:
        clone_result = clone_window_agent_homes(
            source_window.id,
            window_id,
            source_cwd=source_window.cwd,
        )
        cloned_shell_command = (
            clone_resume_command(source_window.shell_command, clone_result)
            or source_window.shell_command
            or get_settings().default_shell
        )
        spec = WindowCloneSpec.local(
            clone_source_from_model(source_window),
            payload,
            CloneReservation.from_result(clone_result),
            cloned_shell_command,
        )
        window = await _create_window_from_clone_spec(
            session,
            client.id,
            spec,
            window_id=window_id,
        )
        source_token = _source_ops_token_for_window(client.id, window_id)
        await session.commit()
        await session.refresh(window)
    except (WindowServiceError, asyncio.CancelledError):
        with contextlib.suppress(Exception):
            await session.rollback()
        remove_window_agent_homes(window_id)
        raise
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()
        remove_window_agent_homes(window_id)
        raise

    schedule_local_window_runtime_start(
        client_id=client.id,
        window_id=window_id,
        cwd=source_window.cwd,
        shell_command=cloned_shell_command,
        agent_ops_token=source_token,
        tmux_manager=tmux_manager,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )
    return WindowMutationResult(
        window=window,
        runtime_tags=runtime_tags_for_window(window, terminal_agent=agent_from_command(window.shell_command)),
    )


def _source_ops_token_for_window(client_id, window_id) -> str | None:
    if not auth_enabled():
        return None
    return create_agent_ops_token(source_client_id=client_id, source_window_id=window_id)


def _require_linked_clone(payload: WindowCloneIn) -> None:
    if payload.mode != "linked":
        raise WindowServiceError(
            501,
            "ephemeral terminal clone collection is not implemented yet",
        )


async def _create_window_from_clone_spec(
    session: AsyncSession,
    client_id,
    spec: WindowCloneSpec,
    *,
    window_id=None,
):
    return await create_window(
        session,
        client_id,
        cwd=spec.cwd,
        shell_command=spec.shell_command,
        window_id=window_id,
        folder_id=spec.folder_id,
        title=spec.title,
        title_manually_overridden=spec.title_manually_overridden,
        folder_manually_overridden=spec.folder_manually_overridden,
        parent_window_id=spec.parent_window_id,
        root_window_id=spec.root_window_id,
        derived_mode=spec.derived_mode,
        derived_context=spec.derived_context,
    )
