from app.contexts.windows.api.agent_launch_config import *  # noqa: F403
from app.contexts.windows.api.agent_record_projection import *  # noqa: F403
from app.contexts.windows.api.response_projection import *  # noqa: F403
from app.contexts.windows.api.window_creation import *  # noqa: F403
from app.contexts.windows.api.window_lifecycle_routes import *  # noqa: F403
from app.contexts.agent_profiles.application import system_config as system_config_service
from app.contexts.windows.api.schemas import AgentRecordSearchOut
from app.contexts.windows.application.agent_record_search import search_agent_record_messages
from app.contexts.windows.application.command_history import read_command_history
from app.contexts.windows.application.title_history import read_title_history
from app.contexts.activity.application.agent_token_usage import load_agent_token_usage_for_window

AgentRecordSearchQuery = Annotated[str, Query(min_length=1, max_length=512)]
AgentRecordSearchLimit = Annotated[int, Query(ge=1, le=50)]
AgentRecordSearchOffset = Annotated[int, Query(ge=0)]


def _normalized_agent_record_search_query(q: str) -> str:
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="search query is required"
        )
    return query


@router.get(
    "/clients/{client_id}/windows/{window_id}/command-history", response_model=CommandHistoryOut
)
async def read_window_command_history(
    client_id: UUID,
    window_id: UUID,
    commands_limit: CommandHistoryLimit = 100,
    commands_offset: CommandHistoryOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> CommandHistoryOut:
    await _require_window_for_agent_record(session, client_id, window_id)
    return await read_command_history(
        session,
        client_id=client_id,
        window_id=window_id,
        limit=commands_limit,
        offset=commands_offset,
    )


@router.get(
    "/clients/{client_id}/windows/{window_id}/title-history", response_model=WindowTitleHistoryOut
)
async def read_window_title_history(
    client_id: UUID,
    window_id: UUID,
    limit: TitleHistoryLimit = 100,
    offset: TitleHistoryOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> WindowTitleHistoryOut:
    await _require_window_for_agent_record(session, client_id, window_id)
    return await read_title_history(
        session,
        client_id=client_id,
        window_id=window_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/clients/{client_id}/windows/{window_id}/agent-record/detail", response_model=AgentRecordOut
)
async def read_window_agent_record_detail(
    client_id: UUID,
    window_id: UUID,
    events_limit: AgentRecordLimit = 100,
    events_offset: AgentRecordOffset = 0,
    session_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> AgentRecordOut:
    await _require_window_for_agent_record(session, client_id, window_id)

    ai_sessions = list(
        await session.scalars(
            select(AiSession)
            .where(AiSession.client_id == client_id, AiSession.virtual_window_id == window_id)
            .order_by(AiSession.created_at, AiSession.id)
        )
    )
    event_filters = [
        Event.client_id == client_id,
        Event.virtual_window_id == window_id,
        Event.kind != "terminal_output",
    ]
    if session_id is not None:
        event_filters.append(Event.ai_session_id == session_id)
    events_total = await session.scalar(
        select(func.count()).select_from(Event).where(*event_filters)
    )
    events = list(
        await session.scalars(
            select(Event)
            .options(selectinload(Event.ai_session))
            .where(*event_filters)
            .order_by(
                Event.created_at,
                case((Event.source_type == EventSourceType.terminal, 1), else_=0),
                Event.id,
            )
            .offset(events_offset)
            .limit(events_limit)
        )
    )
    events = _dedupe_detail_events(events)
    if events and session_id is None:
        event_ids = {event.id for event in events}
        sessions_by_source_id = {ai_session.source_id: ai_session for ai_session in ai_sessions}
        target_session_ids = {
            target_session.id
            for event in events
            if (projection := _project_chat(event)) is not None
            and projection.agent_message_type == "subagent_call"
            and projection.target_session_source_id is not None
            and (target_session := sessions_by_source_id.get(projection.target_session_source_id))
            is not None
        }
        if target_session_ids:
            related_events = list(
                await session.scalars(
                    select(Event)
                    .options(selectinload(Event.ai_session))
                    .where(
                        Event.client_id == client_id,
                        Event.virtual_window_id == window_id,
                        Event.ai_session_id.in_(target_session_ids),
                        Event.kind != "terminal_output",
                    )
                    .order_by(
                        Event.created_at,
                        case((Event.source_type == EventSourceType.terminal, 1), else_=0),
                        Event.id,
                    )
                    .limit(AGENT_RECORD_DETAIL_RELATED_EVENT_LIMIT)
                )
            )
            for event in related_events:
                if event.id in event_ids:
                    continue
                events.append(event)
                event_ids.add(event.id)
    raw_events_total = events_total or 0
    sessions_by_source_id = {ai_session.source_id: ai_session for ai_session in ai_sessions}
    subagent_targets_by_tool_use_id = _subagent_targets_by_tool_use_id(events)
    return AgentRecordOut(
        window_id=window_id,
        sessions=[to_agent_session_out(ai_session) for ai_session in ai_sessions],
        events=[
            to_agent_event_out(event, sessions_by_source_id, subagent_targets_by_tool_use_id)
            for event in events
        ],
        events_total=raw_events_total,
        events_limit=events_limit,
        events_offset=events_offset,
        events_has_more=events_offset + events_limit < raw_events_total,
    )


@router.get("/clients/{client_id}/windows/{window_id}/agent-record", response_model=AgentRecordOut)
async def read_window_agent_record(
    client_id: UUID,
    window_id: UUID,
    events_limit: AgentRecordLimit = 100,
    events_offset: AgentRecordOffset = 0,
    session_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> AgentRecordOut:
    return await read_window_agent_record_detail(
        client_id, window_id, events_limit, events_offset, session_id, session
    )


@router.get(
    "/clients/{client_id}/windows/{window_id}/agent-record/search",
    response_model=AgentRecordSearchOut,
)
async def search_window_agent_record(
    client_id: UUID,
    window_id: UUID,
    q: AgentRecordSearchQuery,
    limit: AgentRecordSearchLimit = 25,
    offset: AgentRecordSearchOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> AgentRecordSearchOut:
    await _require_window_for_agent_record(session, client_id, window_id)
    return await search_agent_record_messages(
        session,
        client_id=client_id,
        window_id=window_id,
        query=_normalized_agent_record_search_query(q),
        limit=limit,
        offset=offset,
    )


@router.get("/clients/{client_id}/agent-record/search", response_model=AgentRecordSearchOut)
async def search_client_agent_records(
    client_id: UUID,
    q: AgentRecordSearchQuery,
    limit: AgentRecordSearchLimit = 25,
    offset: AgentRecordSearchOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> AgentRecordSearchOut:
    await _require_client(session, client_id)
    return await search_agent_record_messages(
        session,
        client_id=client_id,
        query=_normalized_agent_record_search_query(q),
        limit=limit,
        offset=offset,
    )


@router.get("/clients/{client_id}/windows/{window_id}/agent-config", response_model=AgentConfigOut)
async def read_window_agent_config(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    client = await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    if client.runtime is ClientRuntime.local:
        provider = await _agent_provider_for_window(session, window)
        local_agent = _require_supported_agent_capability(provider, "window_config")
        preset_list = await system_config_service.list_system_model_presets(session)
        model_view = agent_config_service.window_agent_model_view(
            local_agent, window_id=str(window_id), preset_list=preset_list
        )
        return _agent_config_out(
            agent_config_service.list_window_agent_config(local_agent, window_id=str(window_id)),
            model=model_view,
        )

    remote_runtime = RemoteRuntime(
        client_id=client_id, registry=_client_connection_registry(request)
    )
    try:
        remote_agent = await _remote_agent_for_window(session, window, remote_runtime)
        payload = await remote_runtime.get_agent_config(
            window_id=window_id,
            agent=remote_agent,
            system_config_files=await _system_config_files_for_remote(session),
        )
    except RemoteClientUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="remote runtime unavailable",
        ) from exc
    except RemoteTerminalError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _agent_config_out(payload)


@router.get("/clients/{client_id}/agent-config/{agent}", response_model=AgentConfigOut)
async def read_client_agent_config(
    request: Request,
    client_id: UUID,
    agent: str,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    client = await _require_client(session, client_id)
    if client.runtime is ClientRuntime.local:
        supported_agent = _require_supported_agent_capability(
            _canonical_provider(agent), "client_config"
        )
        return _agent_config_out(agent_config_service.list_agent_config(supported_agent))

    remote_runtime = RemoteRuntime(
        client_id=client_id, registry=_client_connection_registry(request)
    )
    try:
        payload = await remote_runtime.get_agent_config(
            agent=await _remote_agent_request_id_for_capability(
                remote_runtime, agent, "client_config"
            ),
            system_config_files=await _system_config_files_for_remote(session),
        )
    except RemoteClientUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="remote runtime unavailable",
        ) from exc
    except RemoteTerminalError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _agent_config_out(payload)


@router.get("/clients/{client_id}/system-agent-config", response_model=AgentConfigOut)
async def read_client_system_agent_config(
    request: Request,
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    client = await _require_client(session, client_id)
    if client.runtime is ClientRuntime.local:
        config = await system_config_service.list_system_agent_config(session)
        await session.commit()
        return _agent_config_out(config)

    config = await system_config_service.list_system_agent_config(session)
    await session.commit()
    return _agent_config_out(config)


@router.patch(
    "/clients/{client_id}/windows/{window_id}/agent-config/{section_id}/{item_id:path}",
    response_model=AgentConfigOut,
)
async def update_window_agent_config_item(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    section_id: str,
    item_id: str,
    payload: AgentConfigToggleIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    client = await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    if client.runtime is ClientRuntime.local:
        provider = await _agent_provider_for_window(session, window)
        local_agent = _require_supported_agent_capability(provider, "window_config")
        try:
            return _agent_config_out(
                agent_config_service.set_window_agent_config_item_enabled(
                    local_agent,
                    section_id,
                    item_id,
                    payload.enabled,
                    window_id=str(window_id),
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    remote_runtime = RemoteRuntime(
        client_id=client_id, registry=_client_connection_registry(request)
    )
    try:
        remote_agent = await _remote_agent_for_window(session, window, remote_runtime)
        response_payload = await remote_runtime.set_agent_config_enabled(
            window_id=window_id,
            agent=remote_agent,
            section_id=section_id,
            item_id=item_id,
            enabled=payload.enabled,
            system_config_files=await _system_config_files_for_remote(session),
        )
    except RemoteClientUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="remote runtime unavailable",
        ) from exc
    except RemoteTerminalError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _agent_config_out(response_payload)


async def _system_config_files_for_remote(session: AsyncSession) -> dict[str, object]:
    return await system_config_service.system_agent_config_files_payload(session)


@router.patch(
    "/clients/{client_id}/windows/{window_id}/agent-config/model",
    response_model=AgentConfigOut,
)
async def update_window_agent_config_model(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: AgentConfigModelUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    client = await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")
    update = agent_config_service.WindowAgentModelUpdate(
        model=payload.model,
        codex_model_reasoning_effort=payload.codex_model_reasoning_effort,
        codex_plan_mode_reasoning_effort=payload.codex_plan_mode_reasoning_effort,
        claude_reasoning_effort=payload.claude_reasoning_effort,
        clear_codex_model_reasoning_effort=payload.clear_codex_model_reasoning_effort,
        clear_codex_plan_mode_reasoning_effort=payload.clear_codex_plan_mode_reasoning_effort,
        clear_claude_reasoning_effort=payload.clear_claude_reasoning_effort,
    )
    if client.runtime is ClientRuntime.local:
        provider = await _agent_provider_for_window(session, window)
        local_agent = _require_supported_agent_capability(provider, "window_config")
        preset_list = await system_config_service.list_system_model_presets(session)
        try:
            config = agent_config_service.update_window_agent_model(
                local_agent,
                update,
                window_id=str(window_id),
                preset_list=preset_list,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        model_view = agent_config_service.window_agent_model_view(
            local_agent, window_id=str(window_id), preset_list=preset_list
        )
        return _agent_config_out(config, model=model_view)

    remote_runtime = RemoteRuntime(
        client_id=client_id, registry=_client_connection_registry(request)
    )
    try:
        remote_agent = await _remote_agent_for_window(session, window, remote_runtime)
        response_payload = await remote_runtime.set_agent_config_model(
            window_id=window_id,
            agent=remote_agent,
            payload=payload.model_dump(exclude_none=False),
        )
    except RemoteClientUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="remote runtime unavailable",
        ) from exc
    except RemoteTerminalError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _agent_config_out(response_payload)


@router.get("/windows/{window_id}", response_model=WindowOut)
async def read_local_virtual_window(
    window_id: UUID,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> WindowOut:
    client = await ensure_local_client(session)
    return await _build_window_response(
        session,
        client.id,
        window_id,
        tmux_manager=tmux_manager,
    )


@router.patch("/clients/{client_id}/windows/{window_id}", response_model=WindowOut)
async def update_virtual_window(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: WindowPatchIn,
    session: AsyncSession = Depends(get_session),
) -> WindowOut:
    await _require_client(session, client_id)
    patch_values = {
        field_name: getattr(payload, field_name) for field_name in payload.model_fields_set
    }
    try:
        window = await patch_window(session, client_id, window_id, **patch_values)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FolderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")

    await session.commit()
    await session.refresh(window)
    summary_job = await get_latest_summary_job(session, window.id)
    runtime_tags = await runtime_tags_for_window_out(session, window)
    work_status = await load_work_status(session, client_id, window.id)
    timestamps = await _load_window_overview_timestamps(session, client_id, window.id)
    git_worktree = await load_window_git_worktree_activity(session, window.id)
    agent_token_usage = await load_agent_token_usage_for_window(
        session,
        client_id=client_id,
        window_id=window.id,
    )
    updated = to_window_out(
        window,
        summary_job,
        runtime_tags,
        work_status,
        timestamps,
        git_worktree,
        agent_token_usage,
    )
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree", "window", "search", "title_history"],
        client_id=client_id,
        window_id=window_id,
        reason="window_updated",
    )
    return updated


@router.patch("/windows/{window_id}", response_model=WindowOut)
async def update_local_virtual_window(
    request: Request,
    window_id: UUID,
    payload: WindowPatchIn,
    session: AsyncSession = Depends(get_session),
) -> WindowOut:
    client = await ensure_local_client(session)
    return await update_virtual_window(request, client.id, window_id, payload, session)


@router.delete("/clients/{client_id}/windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_virtual_window(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> None:
    client = await _require_client(session, client_id)
    try:
        await delete_window_service(
            client,
            window_id,
            session,
            tmux_manager,
            _client_connection_registry(request),
        )
    except WindowServiceError as exc:
        raise _service_error_to_http(exc) from exc
    if client.runtime is ClientRuntime.local:
        await aux_terminal_registry_from_state(request.app.state).remove(client_id, window_id)
    else:
        await kill_remote_aux_terminal(
            client_id=client_id,
            parent_window_id=window_id,
            registry=_client_connection_registry(request),
        )
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree", "window", "search"],
        client_id=client_id,
        window_id=window_id,
        reason="window_deleted",
    )


__all__ = [name for name in globals() if not name.startswith("__")]
