from __future__ import annotations

from app.contexts.activity.infrastructure.terminal_recents_repository import (
    DEFAULT_TERMINAL_RECENTS_PAGE_SIZE,
    list_global_terminal_recents,
    list_terminal_recents,
    total_pages,
    touch_terminal_recent,
)

__all__ = [
    "DEFAULT_TERMINAL_RECENTS_PAGE_SIZE",
    "list_global_terminal_recents",
    "list_terminal_recents",
    "total_pages",
    "touch_terminal_recent",
]
