# ruff: noqa: F821
"""Executed into the terminal_work_status package globals."""

from importlib import import_module
from typing import Any

from sqlalchemy import String, cast

_status_service = import_module("app.contexts.activity.application.terminal_work_status.status_service")
globals().update(
    {name: value for name, value in _status_service.__dict__.items() if not name.startswith("__")}
)


@dataclass(frozen=True)
class _ActivityEvent:
    id: UUID
    client_id: UUID
    source_type: EventSourceType
    source_id: str
    kind: str
    virtual_window_id: UUID | None
    ai_session_id: UUID | None
    payload_json: dict[str, Any]
    created_at: datetime


def _activity_event_columns(event_model=Event):
    return (
        event_model.id.label("id"),
        event_model.client_id.label("client_id"),
        cast(event_model.source_type, String).label("source_type"),
        event_model.source_id.label("source_id"),
        event_model.kind.label("kind"),
        event_model.virtual_window_id.label("virtual_window_id"),
        event_model.ai_session_id.label("ai_session_id"),
        event_model.payload_json.label("payload_json"),
        event_model.created_at.label("created_at"),
    )


def _activity_event_from_row(row) -> _ActivityEvent:
    source_type = row.source_type if hasattr(row, "source_type") else row[2]
    if not isinstance(source_type, EventSourceType):
        source_type = EventSourceType(str(source_type))
    return _ActivityEvent(
        id=row.id,
        client_id=row.client_id,
        source_type=source_type,
        source_id=row.source_id,
        kind=row.kind,
        virtual_window_id=row.virtual_window_id,
        ai_session_id=row.ai_session_id,
        payload_json=row.payload_json,
        created_at=row.created_at,
    )


def _activity_events_from_rows(rows) -> list[_ActivityEvent]:
    return [_activity_event_from_row(row) for row in rows]
