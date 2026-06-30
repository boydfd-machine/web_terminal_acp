from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.contexts.windows.application.agent_record_search import (
    agent_record_search_event_filter,
)
from app.models import Event


def test_agent_record_search_filter_matches_recent_partial_index() -> None:
    compiled = str(
        select(Event.id)
        .where(agent_record_search_event_filter())
        .compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "terminal_output" not in compiled
    assert "events.kind IN ('user_message', 'assistant_message')" in compiled
    assert "events.kind = 'system_message'" in compiled
    assert "events.source_type = 'agent_tool_record'" in compiled
    assert "events.kind IN ('response_item', 'event_msg')" in compiled
