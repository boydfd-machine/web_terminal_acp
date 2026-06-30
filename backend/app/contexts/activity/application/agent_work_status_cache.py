from __future__ import annotations

from time import monotonic
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
)
from app.contexts.activity.application.terminal_work_status.projection_status import load_projected_work_statuses

AGENT_WORK_STATUS_CACHE_TTL_SECONDS = 5.0

_status_cache: dict[tuple[UUID, UUID], tuple[float, TerminalWorkStatus]] = {}


def clear_agent_work_status_cache(
    client_id: UUID | None = None,
    window_id: UUID | None = None,
) -> None:
    if client_id is None and window_id is None:
        _status_cache.clear()
        return
    stale_keys = [
        key
        for key in _status_cache
        if (client_id is None or key[0] == client_id) and (window_id is None or key[1] == window_id)
    ]
    for key in stale_keys:
        _status_cache.pop(key, None)


async def cached_agent_work_statuses(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, TerminalWorkStatus]:
    unique_window_ids = list(dict.fromkeys(window_ids))
    if not unique_window_ids:
        return {}

    now = monotonic()
    statuses: dict[UUID, TerminalWorkStatus] = {}
    missing_window_ids: list[UUID] = []
    for window_id in unique_window_ids:
        cached = _status_cache.get((client_id, window_id))
        if cached is not None and now - cached[0] <= AGENT_WORK_STATUS_CACHE_TTL_SECONDS:
            statuses[window_id] = cached[1]
        else:
            missing_window_ids.append(window_id)

    if missing_window_ids:
        loaded = await load_projected_work_statuses(session, client_id, missing_window_ids)
        for window_id, status in loaded.items():
            _status_cache[(client_id, window_id)] = (now, status)
        statuses.update(loaded)

    return statuses
