from app.contexts.windows.api.agent_record_projection import *  # noqa: F403
from app.contexts.windows.api.response_projection import *  # noqa: F403
from app.contexts.windows.api.window_detail_routes import *  # noqa: F403
from app.contexts.windows.api.window_lifecycle_routes import *  # noqa: F403
from app.contexts.activity.application.agent_token_usage import load_agent_token_usage_for_window


@router.delete("/windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_local_virtual_window(
    request: Request,
    window_id: UUID,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> None:
    client = await ensure_local_client(session)
    await delete_virtual_window(request, client.id, window_id, session, tmux_manager)


@router.post("/clients/{client_id}/windows/{window_id}/summary_jobs", response_model=WindowOut)
async def retry_summary_job(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: SummaryJobRetryIn | None = None,
    session: AsyncSession = Depends(get_session),
) -> WindowOut:
    await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")

    allow_override = False if payload is None else payload.allow_title_folder_override
    summary_job = await enqueue_manual_summary_retry(
        session,
        window.id,
        allow_title_folder_override=allow_override,
    )
    await session.commit()
    await session.refresh(window)
    await session.refresh(summary_job)
    runtime_tags = await runtime_tags_for_window_out(session, window)
    work_status = await load_work_status(session, client_id, window.id)
    timestamps = await _load_window_overview_timestamps(session, client_id, window.id)
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
        None,
        agent_token_usage,
    )
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["window"],
        client_id=client_id,
        window_id=window_id,
        reason="summary_retry_queued",
    )
    return updated


@router.post("/windows/{window_id}/summary_jobs", response_model=WindowOut)
async def retry_local_summary_job(
    request: Request,
    window_id: UUID,
    payload: SummaryJobRetryIn | None = None,
    session: AsyncSession = Depends(get_session),
) -> WindowOut:
    client = await ensure_local_client(session)
    return await retry_summary_job(request, client.id, window_id, payload, session)


__all__ = [name for name in globals() if not name.startswith("__")]
