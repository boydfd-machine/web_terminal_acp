from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Event, EventSourceType
from app.services import terminal_work_status


def test_activity_event_projection_casts_source_type_for_postgres() -> None:
    compiled = str(
        select(*terminal_work_status._activity_event_columns(Event)).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "CAST(events.source_type AS VARCHAR) AS source_type" in compiled
    assert "events.source_type AS source_type" not in compiled


def test_activity_event_projection_restores_source_type_enum() -> None:
    event_id = uuid4()
    client_id = uuid4()
    window_id = uuid4()
    created_at = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    event = terminal_work_status._activity_event_from_row(
        type(
            "Row",
            (),
            {
                "id": event_id,
                "client_id": client_id,
                "source_type": EventSourceType.agent_tool_record.value,
                "source_id": "session-1",
                "kind": "assistant_message",
                "virtual_window_id": window_id,
                "ai_session_id": None,
                "payload_json": {"provider": "codex"},
                "created_at": created_at,
            },
        )()
    )

    assert event.source_type is EventSourceType.agent_tool_record
    assert event.virtual_window_id == window_id
