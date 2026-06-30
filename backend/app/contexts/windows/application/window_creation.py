from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth_enabled, create_agent_ops_token
from app.config import get_settings
from app.contexts.windows.domain.runtime_client import RuntimeClient, RuntimeClientKind
from app.contexts.windows.infrastructure.repository import create_window
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.agent_profiles.application import profile_materialization as agent_profile_service
from app.contexts.agent_profiles.application import system_config as system_config_service
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.activity.application.window_runtime_tags import runtime_tags_for_window
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.folder_assignment import assign_window_folder_path
from app.contexts.windows.application.launch_plans import local_window_launch_plan, remote_window_launch_plan
from app.contexts.windows.application.local_runtime_start import schedule_local_window_runtime_start
from app.contexts.windows.application.remote_runtime_start import schedule_remote_window_runtime_start
from app.contexts.windows.application.results import WindowMutationResult
from app.contexts.windows.application.runtime_capabilities import require_remote_launch_capabilities

logger = logging.getLogger(__name__)


async def create_virtual_window_for_client(
    client: RuntimeClient,
    payload: WindowCreateIn,
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
        return await create_remote_virtual_window_for_client(
            client,
            payload,
            session,
            registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    return await create_local_virtual_window_for_client(
        client,
        payload,
        session,
        tmux_manager,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )


async def create_local_virtual_window_for_client(
    client: RuntimeClient,
    payload: WindowCreateIn,
    session: AsyncSession,
    tmux_manager: TmuxManager,
    *,
    session_factory: Callable[[], object],
    ui_event_hub=None,
) -> WindowMutationResult:
    window_id = uuid4()
    try:
        await system_config_service.restore_system_agent_config_files_to_disk(session)
        profile_home = await agent_profile_service.restore_agent_profile_files_to_disk(session)
        await system_config_service.restore_system_agent_config_files_to_disk(session, home=profile_home)
        model_presets = await _model_presets_for_launch(session, payload)
        plan = local_window_launch_plan(
            payload,
            default_shell=get_settings().default_shell,
            model_presets=model_presets,
        )
        agent_config_service.install_system_config_for_window(window_id=str(window_id))
        if plan.agent_profile is not None:
            materialized = agent_profile_service.materialize_builtin_profile_for_window(
                plan.agent_profile.profile_id,
                plan.agent_profile.agent,
                window_id=str(window_id),
                home=profile_home,
            )
            if materialized is None:
                agent_profile_service.materialize_agent_profile_for_window(
                    plan.agent_profile.profile_id,
                    plan.agent_profile.agent,
                    window_id=str(window_id),
                    home=profile_home,
                )
        if plan.agent_config_selection is not None:
            agent_config_service.apply_agent_config_selection(
                plan.agent_config_selection,
                window_id=str(window_id),
                protect_system_config_skills=plan.agent_profile is not None,
            )
        if plan.agent_model_agent is not None:
            if plan.agent_model_selection is not None:
                agent_config_service.save_window_agent_model_selection(
                    plan.agent_model_agent,
                    plan.agent_model_selection,
                    window_id=str(window_id),
                )
            agent_config_service.materialize_agent_model_settings_for_window(
                plan.agent_model_agent,
                plan.agent_model_settings,
                window_id=str(window_id),
            )
        source_token = _source_ops_token_for_window(client.id, window_id)
        window = await create_window(
            session,
            client.id,
            cwd=plan.cwd,
            shell_command=plan.shell_command,
            window_id=window_id,
            derived_context=_agent_model_derived_context(plan.agent_model_settings),
        )
        await assign_window_folder_path(session, client.id, window, payload.folder_path)
        await session.commit()
        await session.refresh(window)
    except (WindowServiceError, asyncio.CancelledError):
        with contextlib.suppress(Exception):
            await session.rollback()
        raise
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()
        raise

    schedule_local_window_runtime_start(
        client_id=client.id,
        window_id=window_id,
        cwd=plan.cwd,
        shell_command=plan.shell_command,
        agent_ops_token=source_token,
        tmux_manager=tmux_manager,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )
    return WindowMutationResult(
        window=window,
        runtime_tags=runtime_tags_for_window(window, terminal_agent=plan.terminal_agent),
    )


async def create_remote_virtual_window_for_client(
    client: RuntimeClient,
    payload: WindowCreateIn,
    session: AsyncSession,
    registry: ClientConnectionRegistry,
    *,
    session_factory: Callable[[], object],
    ui_event_hub=None,
) -> WindowMutationResult:
    client_id = client.id
    connection = registry.get(client_id)
    if connection is None or getattr(connection, "closed", False):
        logger.warning(
            "remote runtime unavailable during window create",
            extra={
                "client_id": str(client_id),
                "reason": "no_connection" if connection is None else "connection_closed",
            },
        )
        raise WindowServiceError(503, "remote runtime unavailable")

    await system_config_service.restore_system_agent_config_files_to_disk(session)
    system_config_files = await system_config_service.system_agent_config_files_payload(session)
    model_presets = await _model_presets_for_launch(session, payload)
    plan = remote_window_launch_plan(payload, model_presets=model_presets)
    remote_runtime = RemoteRuntime(client_id=client_id, registry=registry)
    try:
        await require_remote_launch_capabilities(payload, remote_runtime)
    except RemoteClientUnavailable as exc:
        raise WindowServiceError(503, "remote runtime unavailable") from exc
    except RemoteTerminalError as exc:
        raise WindowServiceError(502, str(exc)) from exc

    try:
        window = await create_window(
            session,
            client_id,
            cwd=plan.cwd,
            shell_command=plan.shell_command,
            derived_context=_agent_model_derived_context(_model_settings_from_remote_payload(plan.agent_model_payload)),
        )
        await assign_window_folder_path(session, client_id, window, payload.folder_path)
        await session.commit()
        await session.refresh(window)
    except (WindowServiceError, asyncio.CancelledError):
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
        cwd=plan.cwd,
        shell_command=plan.shell_command,
        agent_config_selection=plan.agent_config_payload,
        system_config_files=system_config_files,
        agent_model_settings=plan.agent_model_payload,
        agent_model_agent=plan.agent_model_agent,
        agent_profile_id=plan.agent_profile.profile_id if plan.agent_profile else None,
        agent_profile_agent=plan.agent_profile.agent if plan.agent_profile else None,
        agent_ops_token=source_token,
        registry=registry,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )
    return WindowMutationResult(
        window=window,
        runtime_tags=runtime_tags_for_window(window, terminal_agent=plan.runtime_terminal_agent),
    )


def _source_ops_token_for_window(client_id, window_id) -> str | None:
    if not auth_enabled():
        return None
    return create_agent_ops_token(source_client_id=client_id, source_window_id=window_id)


def _agent_model_derived_context(
    settings: agent_config_service.ResolvedAgentModelSettings | None,
) -> dict[str, object] | None:
    payload = agent_config_service.safe_agent_model_settings_payload(settings)
    return {"agent_model": payload} if payload is not None else None


def _model_settings_from_remote_payload(
    payload: dict[str, object] | None,
) -> agent_config_service.ResolvedAgentModelSettings | None:
    return agent_config_service.resolved_agent_model_settings_from_payload(payload)


async def _model_presets_for_launch(
    session: AsyncSession,
    payload: WindowCreateIn,
) -> agent_config_service.SystemModelPresetList | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    return await system_config_service.list_system_model_presets(session)
