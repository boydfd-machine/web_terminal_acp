import asyncio
import contextlib
import logging
import posixpath
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Text, and_, case, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.platform.plugins.agent_plugins import get_agent_plugin_registry, list_agent_client_descriptors
from app.platform.plugins.agent_tools import agent_activity_source_types, get_agent_tool_registry
from app.platform.plugins.agent_tools.common import fallback_projection
from app.platform.plugins.agent_tools.types import AgentChatProjection, AgentEventProjection, AgentToolAdapter
from app.contexts.windows.application.agent_event_projection import (
    projection_target_source_id as _projection_target_source_id,
    target_session_id_for_source as _target_session_id_for_source,
)
from app.config import get_settings
from app.db import SessionLocal, get_session
from app.contexts.windows.domain.remote_agents import RemoteAgentCatalog
from app.contexts.windows.domain.runtime_client import RuntimeClient
from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    Event,
    EventSourceType,
    SummaryJob,
    TerminalRecentUsage,
    VirtualWindow,
    WindowStatus,
)
from app.contexts.clients.application.client_lookup import ensure_local_client, get_client
from app.contexts.workspace.application.summary_job_access import (
    enqueue_manual_summary_retry,
    get_latest_summary_job,
)
from app.contexts.terminal_runtime.application.git_worktree_queries import get_window_git_binding, list_git_worktree_runs
from app.contexts.windows.application.window_lookup import (
    FolderNotFoundError,
    create_window,
    get_window_for_client,
    list_window_title_history,
    patch_window,
)
from app.platform.ui_events import ui_event_hub_from_state
from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.agent_profiles.application import profile_materialization as agent_profile_service
from app.contexts.agent_profiles.application.capabilities import (
    AgentClientCapabilityError,
    canonical_provider as service_canonical_provider,
    require_local_agent_capability as service_require_local_agent_capability,
    require_supported_agent_capability as service_require_supported_agent_capability,
    require_supported_provider as service_require_supported_provider,
)
from app.contexts.agent_profiles.application.config_projection import agent_config_out
from app.contexts.terminal_runtime.application.aux_terminal import (
    aux_terminal_registry_from_state,
    kill_remote_aux_terminal,
)
from app.contexts.activity.api.schemas import (
    AgentEventOut,
    AgentEventProjectionOut,
    AgentSessionOut,
    GitWorktreeActivityOut,
)
from app.contexts.agent_profiles.api.schemas import (
    AgentConfigOut,
    AgentConfigToggleIn,
    AgentConfigModelUpdateIn,
    AgentClientListOut,
    CursorOfficialModelListOut,
)
from app.contexts.agent_profiles.application.cursor_official_models import (
    list_cursor_official_models_for_client,
)
from app.contexts.windows.api.schemas import (
    AgentChatMessageOut,
    AgentChatRecordOut,
    AgentRecordOut,
    CommandHistoryItemOut,
    CommandHistoryOut,
    GitWorktreeRunListOut,
    GitWorktreeRunOut,
    SummaryJobOut,
    SummaryJobRetryIn,
    WindowCreateIn,
    WindowCloneIn,
    WindowOut,
    WindowPatchIn,
    WindowTitleHistoryItemOut,
    WindowTitleHistoryOut,
)
from app.platform.common_schemas import AgentConfigSelectionIn
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.terminal_runtime.application.git_worktree_agent_markers import materialize_agent_worktree_markers
from app.contexts.terminal_runtime.application.git_worktree_coordinator import process_git_worktree_snapshot_refresh
from app.platform.polling_response_cache import (
    CachedJsonResponse,
    begin_response_cache_refresh,
    cached_or_stale_json_response_async,
    finish_response_cache_refresh,
    response_cache_scope,
    store_json_response_async,
)
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.folder_assignment import assign_window_folder_path
from app.contexts.windows.application.launch_plans import (
    agent_selection_from_schema,
    agent_selection_payload,
    launch_agent_command,
    launch_agent_profile_id,
    launch_agent_provider,
    local_window_launch_plan,
    remote_window_launch_plan,
)
from app.contexts.windows.application.runtime_capabilities import require_remote_launch_capabilities
from app.contexts.windows.application.runtime_client import runtime_client_from_model
from app.contexts.windows.application.window_deletion import delete_virtual_window_for_client as delete_window_service
from app.contexts.windows.application.window_projection import (
    WindowOverviewTimestamps as _WindowOverviewTimestamps,
    agent_command_for_window as _agent_command_for_window,
    agent_provider_for_window as _agent_provider_for_window,
    load_window_overview_timestamps as _load_window_overview_timestamps,
    runtime_tags_for_window_out,
    to_agent_session_out,
    to_summary_job_out,
    to_window_out,
)
from app.contexts.activity.domain.event_kinds import AGENT_WORK_PRESENCE_KIND
from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
    load_work_status,
    long_idle_work_status,
    to_work_status_out,
)
from app.contexts.activity.application.window_git_worktree_activity import load_window_git_worktree_activity
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager
from app.contexts.activity.application.window_runtime_tags import agent_from_command, runtime_tags_for_window

router = APIRouter(prefix="/api", tags=["windows"])
logger = logging.getLogger(__name__)
REMOTE_CREATE_WINDOW_TIMEOUT_SECONDS = 60.0
LOCAL_CREATE_WINDOW_TIMEOUT_SECONDS = 30.0

AgentRecordLimit = Annotated[int, Query(ge=1, le=200)]
AgentRecordOffset = Annotated[int, Query(ge=0)]
AgentChatRole = Literal["all", "user", "agent", "subagent_call", "subagent_result"]
AgentClientCapability = Literal["launch", "client_config", "window_config", "profile_config"]
CommandHistoryLimit = Annotated[int, Query(ge=1, le=200)]
CommandHistoryOffset = Annotated[int, Query(ge=0)]
TitleHistoryLimit = Annotated[int, Query(ge=1, le=200)]
TitleHistoryOffset = Annotated[int, Query(ge=0)]
_PROVIDER_ALIASES = {"claude": "claude_code", "cursor": "cursor_cli", "agent": "cursor_cli"}
_COMMAND_SEGMENT_PATTERN = re.compile(r"&&|\|\||[;|]")
_ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_COMMAND_WRAPPERS = {"command", "env", "sudo"}
_REMOTE_CAPABILITY_DEFAULTS: dict[AgentClientCapability, bool] = {
    "launch": True,
    "client_config": True,
    "window_config": True,
    "profile_config": True,
}
AGENT_RECORD_CHAT_EVENT_BATCH_SIZE = 500
AGENT_RECORD_DETAIL_RELATED_EVENT_LIMIT = 500


@router.get("/clients/{client_id}/agent-clients", response_model=AgentClientListOut)
async def read_agent_clients(
    client_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AgentClientListOut:
    client = await _require_client(session, client_id)
    if client.runtime is not ClientRuntime.local:
        runtime = RemoteRuntime(
            client_id=client_id,
            registry=request.app.state.client_connections,
        )
        try:
            return AgentClientListOut.model_validate(await runtime.list_agent_clients())
        except RemoteClientUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": "remote client unavailable", "reason": exc.reason},
            ) from exc
        except RemoteTerminalError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    return AgentClientListOut(
        agent_clients=[
            {
                "id": descriptor.id,
                "provider_id": descriptor.provider_id,
                "label": descriptor.label,
                "aliases": list(descriptor.aliases),
                "default_command": descriptor.default_command,
                "command_names": list(descriptor.command_names),
                "capabilities": asdict(descriptor.capabilities),
            }
            for descriptor in list_agent_client_descriptors()
        ]
    )


@router.get(
    "/clients/{client_id}/agent-clients/cursor/official-models",
    response_model=CursorOfficialModelListOut,
)
async def read_cursor_official_models(
    client_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CursorOfficialModelListOut:
    await _require_client(session, client_id)
    try:
        models = await list_cursor_official_models_for_client(
            session=session,
            client_id=client_id,
            registry=request.app.state.client_connections,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return CursorOfficialModelListOut(models=models)


_RuntimeClient = RuntimeClient


def _runtime_client_from_model(client: Client) -> RuntimeClient:
    return runtime_client_from_model(client)


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


def _canonical_provider(provider: str) -> str:
    return service_canonical_provider(provider)


def _payload_provider(event: Event) -> str | None:
    provider = event.payload_json.get("provider")
    if isinstance(provider, str) and provider.strip():
        return _canonical_provider(provider.strip())
    return None


def _adapter_for_event(event: Event) -> AgentToolAdapter | None:
    registry = get_agent_tool_registry()

    if event.ai_session is not None and event.ai_session.provider:
        with contextlib.suppress(ValueError):
            return registry.by_provider(_canonical_provider(event.ai_session.provider))

    if event.source_type is EventSourceType.agent_tool_record:
        provider = _payload_provider(event)
        if provider is not None:
            with contextlib.suppress(ValueError):
                return registry.by_provider(provider)
        return None

    with contextlib.suppress(KeyError, ValueError):
        return registry.by_source_type(event.source_type)
    return None


def _projection_out(
    projection: AgentEventProjection,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventProjectionOut:
    sessions_by_source_id = sessions_by_source_id or {}
    target_session_source_id = _projection_target_source_id(
        projection,
        subagent_targets_by_tool_use_id or {},
    )
    return AgentEventProjectionOut(
        tone=projection.tone,
        label=projection.label,
        body=projection.body,
        body_format=projection.body_format,
        subtype=projection.subtype,
        agent_message_type=_agent_message_type(projection.agent_message_type),
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_id=_target_session_id_for_source(target_session_source_id, sessions_by_source_id),
        target_session_source_id=target_session_source_id,
    )


def _project_event(
    event: Event,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventProjectionOut:
    adapter = _adapter_for_event(event)
    projection: AgentEventProjection | None = None
    if adapter is not None:
        with contextlib.suppress(Exception):
            projection = adapter.project_event(event)
    return _projection_out(
        projection or fallback_projection(event),
        sessions_by_source_id,
        subagent_targets_by_tool_use_id,
    )


def to_agent_event_out(
    event: Event,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventOut:
    return AgentEventOut(
        id=event.id,
        ai_session_id=event.ai_session_id,
        source_type=event.source_type.value,
        source_id=event.source_id,
        kind=event.kind,
        payload_json=event.payload_json,
        projection=_project_event(event, sessions_by_source_id, subagent_targets_by_tool_use_id),
        created_at=event.created_at,
    )


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _project_chat(event: Event) -> AgentChatProjection | None:
    adapter = _adapter_for_event(event)
    if adapter is not None:
        with contextlib.suppress(Exception):
            return adapter.project_chat(event)
    return None


def _agent_message_type(value: str | None) -> Literal["agent", "subagent_call", "subagent_result"] | None:
    if value in {"agent", "subagent_call", "subagent_result"}:
        return value
    return None


__all__ = [name for name in globals() if not name.startswith("__")]
