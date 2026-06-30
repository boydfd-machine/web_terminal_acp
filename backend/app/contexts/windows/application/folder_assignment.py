from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VirtualWindow
from app.contexts.workspace.application.folder_access import get_or_create_folder_by_path
from app.contexts.windows.application.errors import WindowServiceError


async def assign_window_folder_path(
    session: AsyncSession,
    client_id: UUID,
    window: VirtualWindow,
    folder_path: str | None,
) -> None:
    if not folder_path:
        return
    try:
        folder = await get_or_create_folder_by_path(session, client_id, folder_path)
    except ValueError as exc:
        raise WindowServiceError(400, str(exc)) from exc
    window.folder_id = folder.id
    window.folder_manually_overridden = True
