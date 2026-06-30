from __future__ import annotations

from uuid import UUID

from app.platform.ui_events import ui_event_hub_from_state


class ClientUiEvents:
    def __init__(self, app_state: object | None) -> None:
        self._app_state = app_state

    async def publish(
        self,
        resources: list[str],
        *,
        client_id: UUID,
        reason: str,
    ) -> None:
        if self._app_state is None:
            return
        await ui_event_hub_from_state(self._app_state).publish_invalidation(
            resources,
            client_id=client_id,
            reason=reason,
        )
