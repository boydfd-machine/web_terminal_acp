from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.api.schemas import ManualWorkStatusIn, WorkStatusOut
from app.contexts.activity.application.terminal_work_status import (
    set_manual_work_status,
    to_work_status_out,
)
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.db import get_session
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api", tags=["work-status"])


async def _require_client(session: AsyncSession, client_id: UUID) -> None:
    if await get_client(session, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")


@router.patch(
    "/clients/{client_id}/windows/{window_id}/work-status",
    response_model=WorkStatusOut,
)
async def update_manual_work_status(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: ManualWorkStatusIn,
    session: AsyncSession = Depends(get_session),
) -> WorkStatusOut:
    await _require_client(session, client_id)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found")

    try:
        work_status = await set_manual_work_status(session, window, payload.state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await session.commit()
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["window", "terminal_notifications"],
        client_id=client_id,
        window_id=window_id,
        reason="manual_work_status",
    )
    return to_work_status_out(work_status)
