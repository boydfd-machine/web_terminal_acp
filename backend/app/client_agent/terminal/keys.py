from __future__ import annotations

from uuid import UUID

def _attachment_key(window_id: UUID | str, view_id: UUID | str | None = None) -> str:
    return str(view_id or window_id)
