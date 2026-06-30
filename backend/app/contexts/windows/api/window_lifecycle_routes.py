import json

from app.contexts.windows.api.agent_launch_config import *  # noqa: F403
from app.contexts.windows.api.agent_record_projection import *  # noqa: F403
from app.contexts.windows.api.response_projection import *  # noqa: F403
from app.contexts.windows.api.window_creation import *  # noqa: F403
from app.contexts.windows.api.window_agent_model_metadata import (
    read_remote_window_agent_model_metadata,
)
from app.contexts.agent_profiles.application import system_config as system_config_service

from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.window_cloning import (
    clone_virtual_window_for_client as clone_window_service,
)
from app.contexts.windows.application.window_creation import (
    create_virtual_window_for_client as create_window_service,
)
from app.contexts.terminal_runtime.application.runtime_provider import TmuxTarget
from app.contexts.activity.application.agent_token_usage import load_agent_token_usage_for_window


def _service_error_to_http(exc: WindowServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/clients/{client_id}/windows", response_model=WindowOut)
async def create_virtual_window(
    request: Request,
    client_id: UUID,
    payload: WindowCreateIn,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> WindowOut:
    client = _runtime_client_from_model(await _require_client(session, client_id))
    await session.commit()
    try:
        result = await create_window_service(
            client,
            payload,
            session,
            tmux_manager,
            _client_connection_registry(request),
            session_factory=_background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
        )
    except WindowServiceError as exc:
        raise _service_error_to_http(exc) from exc
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree", "window", "search"],
        client_id=client_id,
        window_id=result.window.id,
        reason="window_created",
    )
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


@router.post("/clients/{client_id}/windows/{window_id}/clone", response_model=WindowOut)
async def clone_virtual_window(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: WindowCloneIn = WindowCloneIn(),
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> WindowOut:
    client_model = await _require_client(session, client_id)
    source_window = await get_window_for_client(session, client_id, window_id)
    if source_window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    client = _runtime_client_from_model(client_model)
    await session.commit()
    try:
        result = await clone_window_service(
            client,
            source_window,
            payload,
            session,
            tmux_manager,
            _client_connection_registry(request),
            session_factory=_background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
        )
    except WindowServiceError as exc:
        raise _service_error_to_http(exc) from exc
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree", "window", "search"],
        client_id=client_id,
        window_id=result.window.id,
        reason="window_cloned",
    )
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


@router.post("/windows", response_model=WindowOut)
async def create_local_virtual_window(
    request: Request,
    payload: WindowCreateIn,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> WindowOut:
    client = _runtime_client_from_model(await ensure_local_client(session))
    await session.commit()
    try:
        result = await create_window_service(
            client,
            payload,
            session,
            tmux_manager,
            session_factory=_background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
        )
    except WindowServiceError as exc:
        raise _service_error_to_http(exc) from exc
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree", "window", "search"],
        client_id=client.id,
        window_id=result.window.id,
        reason="window_created",
    )
    return to_window_out(result.window, runtime_tags=result.runtime_tags)


@router.get("/clients/{client_id}/windows/{window_id}", response_model=WindowOut)
async def read_virtual_window(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> WindowOut | Response:
    cache_key = ("window-v4", response_cache_scope(session), client_id, window_id)
    cached = await _cached_or_stale_response(cache_key)
    if cached is not None:
        cached_incomplete = _cached_response_incomplete(cached.response)
        if not cached.expired and not cached_incomplete:
            return cached.response
        if not cached_incomplete:
            _refresh_window_response_cache(
                cache_key,
                client_id,
                window_id,
                registry=_client_connection_registry(request),
                tmux_manager=tmux_manager,
            )
            return cached.response

    return await _build_window_response(
        session,
        client_id,
        window_id,
        request=request,
        cache_key=cache_key,
        tmux_manager=tmux_manager,
    )


async def _build_window_response(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    *,
    request: Request | None = None,
    registry: ClientConnectionRegistry | None = None,
    cache_key: tuple[object, ...] | None = None,
    tmux_manager: TmuxManager | None = None,
) -> Response:
    client = await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    if tmux_manager is not None and await _backfill_tmux_window_index(window, tmux_manager):
        await session.commit()
    summary_job = await get_latest_summary_job(session, window.id)
    runtime_tags = await runtime_tags_for_window_out(session, window)
    work_status = await load_work_status(session, client_id, window.id)
    timestamps = await _load_window_overview_timestamps(session, client_id, window.id)
    await _materialize_window_git_worktree_from_agent_marker(
        session,
        client,
        client_id=client_id,
        window_id=window.id,
        request=request,
        registry=registry,
    )
    git_worktree = await load_window_git_worktree_activity(session, window.id)
    agent_token_usage = await load_agent_token_usage_for_window(
        session,
        client_id=client_id,
        window_id=window.id,
    )
    agent_model_metadata = await _client_window_agent_model_metadata(
        session,
        client,
        window,
        request=request,
        registry=registry,
    )
    payload = to_window_out(
        window,
        summary_job,
        runtime_tags,
        work_status,
        timestamps,
        git_worktree,
        agent_token_usage,
        agent_model_metadata=agent_model_metadata,
    )
    return await store_json_response_async(
        cache_key or ("window-v4", response_cache_scope(session), client_id, window_id),
        payload,
        resources={"window"},
        client_id=client_id,
    )


async def _materialize_window_git_worktree_from_agent_marker(
    session: AsyncSession,
    client: Client,
    *,
    client_id: UUID,
    window_id: UUID,
    request: Request | None = None,
    registry: ClientConnectionRegistry | None = None,
) -> None:
    if await get_window_git_binding(session, window_id) is not None:
        return
    if registry is None:
        registry = _client_connection_registry(request) if request is not None else None
    materialized = await materialize_agent_worktree_markers(
        session,
        client_id=client_id,
        window_ids=(window_id,),
        registry=registry,
    )
    if window_id not in materialized:
        return
    await process_git_worktree_snapshot_refresh(
        session,
        client_id=client_id,
        window_id=window_id,
        registry=registry,
        client_runtime=client.runtime,
    )
    await session.commit()


async def _cached_or_stale_response(cache_key: tuple[object, ...]) -> CachedJsonResponse | None:
    return await cached_or_stale_json_response_async(cache_key)


def _cached_response_incomplete(response: Response) -> bool:
    payload = _cached_response_payload(response)
    if payload is None:
        return False
    return _cached_response_missing_tmux_window_index(
        payload
    ) or _cached_response_missing_token_limit(payload)


def _cached_response_payload(response: Response) -> dict[str, object] | None:
    content = getattr(response, "body", b"")
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _cached_response_missing_tmux_window_index(payload: dict[str, object]) -> bool:
    return (
        payload.get("tmux_window_index") is None
        and payload.get("tmux_session") is not None
        and payload.get("tmux_window_id") is not None
    )


def _cached_response_missing_token_limit(payload: dict[str, object]) -> bool:
    usage = payload.get("agent_token_usage")
    if not isinstance(usage, dict):
        return False
    total = usage.get("total")
    if not isinstance(total, dict):
        return False
    total_tokens = total.get("total_tokens")
    shell_command = payload.get("shell_command")
    terminal_agent = agent_from_command(shell_command) if isinstance(shell_command, str) else None
    return (
        terminal_agent in {"claude_code", "codex"}
        and isinstance(total_tokens, int)
        and total_tokens > 0
        and usage.get("context_window") is None
        and usage.get("auto_compact_token_limit") is None
    )


def _refresh_window_response_cache(
    cache_key: tuple[object, ...],
    client_id: UUID,
    window_id: UUID,
    *,
    registry: ClientConnectionRegistry | None = None,
    tmux_manager: TmuxManager | None = None,
) -> None:
    if not begin_response_cache_refresh(cache_key):
        return

    async def refresh_window() -> None:
        try:
            async with SessionLocal() as refresh_session:
                await _build_window_response(
                    refresh_session,
                    client_id,
                    window_id,
                    registry=registry,
                    cache_key=cache_key,
                    tmux_manager=tmux_manager,
                )
        except Exception:
            logger.exception(
                "window response cache refresh failed", extra={"cache_key": repr(cache_key)}
            )
        finally:
            finish_response_cache_refresh(cache_key)

    asyncio.create_task(refresh_window())


async def _client_window_agent_model_metadata(
    session: AsyncSession,
    client: Client,
    window: VirtualWindow,
    *,
    request: Request | None = None,
    registry: ClientConnectionRegistry | None = None,
) -> dict[str, object] | None:
    if client.runtime is ClientRuntime.local:
        provider = await _agent_provider_for_window(session, window)
        try:
            local_agent = _require_supported_agent_capability(provider, "window_config")
        except HTTPException:
            return None
        return agent_config_service.window_agent_model_metadata(
            local_agent, window_id=str(window.id)
        )

    if registry is None:
        registry = _client_connection_registry(request) if request is not None else None
    if registry is None:
        return None

    remote_runtime = RemoteRuntime(
        client_id=client.id,
        registry=registry,
        request_timeout=2.0,
    )
    try:
        remote_agent = await _remote_agent_for_window(session, window, remote_runtime)
        payload = await remote_runtime.get_agent_config(
            window_id=window.id,
            agent=remote_agent,
            system_config_files=await system_config_service.system_agent_config_files_payload(session),
        )
    except (HTTPException, RemoteClientUnavailable, RemoteTerminalError):
        return None
    metadata = payload.get("model_metadata")
    if isinstance(metadata, dict):
        return metadata
    return await read_remote_window_agent_model_metadata(
        remote_runtime,
        client,
        remote_agent=remote_agent,
        window_id=window.id,
    )


async def _backfill_tmux_window_index(window: VirtualWindow, tmux_manager: TmuxManager) -> bool:
    if (
        window.tmux_window_index is not None
        or window.tmux_session is None
        or window.tmux_window_id is None
    ):
        return False
    window_index = await tmux_manager.window_index(
        TmuxTarget(session=window.tmux_session, window_id=window.tmux_window_id)
    )
    if window_index is None:
        return False
    window.tmux_window_index = window_index
    return True


async def _require_window_for_agent_record(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
) -> VirtualWindow:
    await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    return window


@router.get(
    "/clients/{client_id}/windows/{window_id}/agent-record/chat", response_model=AgentChatRecordOut
)
async def read_window_agent_record_chat(
    client_id: UUID,
    window_id: UUID,
    messages_limit: AgentRecordLimit = 30,
    messages_offset: AgentRecordOffset = 0,
    role: AgentChatRole = "all",
    messages_order: AgentChatOrder = "earliest",
    session_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> AgentChatRecordOut:
    await _require_window_for_agent_record(session, client_id, window_id)
    ai_sessions = list(
        await session.scalars(
            select(AiSession)
            .where(AiSession.client_id == client_id, AiSession.virtual_window_id == window_id)
            .order_by(AiSession.created_at, AiSession.id)
        )
    )
    base_event_filters = [
        Event.client_id == client_id,
        Event.virtual_window_id == window_id,
    ]
    event_filters = [
        *base_event_filters,
        or_(
            Event.kind.in_(("user_message", "assistant_message")),
            and_(
                Event.kind == "system_message",
                Event.source_type == EventSourceType.agent_tool_record,
            ),
            Event.kind.in_(("response_item", "event_msg")),
        ),
    ]
    if session_id is not None:
        base_event_filters.append(Event.ai_session_id == session_id)
        event_filters.append(Event.ai_session_id == session_id)
    page = await _load_chat_message_page(
        session,
        event_filters=event_filters,
        target_event_filters=base_event_filters,
        role=role,
        sessions_by_source_id={ai_session.source_id: ai_session for ai_session in ai_sessions},
        messages_limit=messages_limit,
        messages_offset=messages_offset,
        messages_order=messages_order,
    )
    return AgentChatRecordOut(
        window_id=window_id,
        messages=page.messages,
        messages_total=page.total,
        messages_total_exact=page.total_exact,
        messages_limit=messages_limit,
        messages_offset=messages_offset,
        messages_has_more=page.has_more,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
