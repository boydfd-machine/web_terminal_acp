from __future__ import annotations

from uuid import UUID

from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.stale_window_cleanup import ClientStaleWindowCleanup
from app.services.runtime.protocol import AgentMessage


def cleanup_register(
    cleanup: ClientStaleWindowCleanup | None,
    window_id: UUID,
    runtime_window: ClientRuntimeWindow,
) -> None:
    if cleanup is not None:
        cleanup.register_window(window_id, runtime_window)


def cleanup_call(
    cleanup: ClientStaleWindowCleanup | None,
    method_name: str,
    window_id: UUID | None,
    *,
    when: bool = True,
) -> None:
    if when and window_id is not None and cleanup is not None:
        getattr(cleanup, method_name)(window_id)


def cleanup_mark_terminal_viewed(
    cleanup: ClientStaleWindowCleanup | None,
    message: AgentMessage,
    window_id: UUID,
) -> None:
    if isinstance(message.payload.get("activity"), str) and message.payload["activity"] == "terminal_viewed":
        cleanup_call(cleanup, "touch_window", window_id)
