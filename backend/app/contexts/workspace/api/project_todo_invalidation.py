from __future__ import annotations

from uuid import UUID

from fastapi import Request

from app.platform.ui_events import ui_event_hub_from_state


async def publish_project_todo_invalidation(
    request: Request,
    client_id: UUID,
    *,
    window_id: UUID | None = None,
    reason: str,
) -> None:
    resources = ["project_todos"]
    if window_id is not None:
        resources.extend(["window", "terminal_recents"])
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        resources,
        client_id=client_id,
        window_id=window_id,
        reason=reason,
    )
