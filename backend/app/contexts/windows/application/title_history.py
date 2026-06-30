from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.windows.infrastructure.repository import list_window_title_history
from app.contexts.windows.api.schemas import WindowTitleHistoryItemOut, WindowTitleHistoryOut


async def read_title_history(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
) -> WindowTitleHistoryOut:
    items, total = await list_window_title_history(
        session,
        client_id,
        window_id,
        limit=limit,
        offset=offset,
    )
    return WindowTitleHistoryOut(
        window_id=window_id,
        items=[
            WindowTitleHistoryItemOut(
                id=item.id,
                title=item.title,
                summary=item.summary,
                source=item.source,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )
