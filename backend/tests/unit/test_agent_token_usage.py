from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.activity.application.agent_token_usage import (
    agent_token_usage_from_events,
    agent_token_usage_events_statement,
    load_agent_token_usage_for_window,
    payload_is_token_usage_only,
    token_usage_from_payload,
)
from app.contexts.activity.api.schemas import AgentTokenUsageCountsOut, AgentTokenUsageOut
from app.contexts.windows.application.window_projection import (
    token_usage_with_window_model_metadata,
    window_agent_config_model_metadata,
)
from app.model_base import Base
from app.models import Event, EventSourceType
from app.models.windows import VirtualWindow


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


def test_token_usage_extracts_codex_context_total_and_cached_tokens() -> None:
    payload = {
        "provider": "codex",
        "raw_type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 400,
                    "output_tokens": 50,
                    "reasoning_output_tokens": 12,
                    "total_tokens": 1050,
                },
                "last_token_usage": {
                    "input_tokens": 700,
                    "cached_input_tokens": 320,
                    "output_tokens": 30,
                    "reasoning_output_tokens": 8,
                    "total_tokens": 730,
                },
                "model_context_window": 258400,
                "model_auto_compact_token_limit": 200000,
            },
        },
    }

    snapshot = token_usage_from_payload(payload)

    assert snapshot is not None
    assert payload_is_token_usage_only(payload) is True
    assert snapshot.context is not None
    assert snapshot.context.total_tokens == 730
    assert snapshot.context.cached_input_tokens == 320
    assert snapshot.total.total_tokens == 1050
    assert snapshot.total.cached_input_tokens == 400
    assert snapshot.context_window == 258400
    assert snapshot.auto_compact_token_limit == 200000


def test_agent_token_usage_events_query_uses_index_order_without_terminal_tie_breaker() -> None:
    statement = agent_token_usage_events_statement(client_id=uuid4(), window_id=uuid4())

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "events.source_type IN" in compiled
    assert "ORDER BY events.created_at, events.id" in compiled
    assert "CASE WHEN" not in compiled


def test_token_usage_projection_uses_window_model_limits_when_no_usage_events() -> None:
    window = VirtualWindow(
        title="Claude",
        derived_context={
            "agent_model": {
                "provider": "anthropic_compatible",
                "model": "sonnet-y",
                "context_window": 200000,
                "auto_compact_token_limit": 150000,
            }
        },
    )

    usage = token_usage_with_window_model_metadata(window, None)

    assert usage is not None
    assert usage.context_window == 200000
    assert usage.auto_compact_token_limit == 150000
    assert usage.total.total_tokens == 0
    assert usage.providers == ["anthropic_compatible"]


def test_token_usage_projection_keeps_compact_limit_without_context_window() -> None:
    window = VirtualWindow(
        title="Claude",
        derived_context={
            "agent_model": {
                "provider": "anthropic_compatible",
                "model": "sonnet-y",
                "auto_compact_token_limit": 150000,
            }
        },
    )

    usage = token_usage_with_window_model_metadata(window, None)

    assert usage is not None
    assert usage.context_window is None
    assert usage.auto_compact_token_limit == 150000
    assert usage.total.total_tokens == 0
    assert usage.providers == ["anthropic_compatible"]


def test_token_usage_projection_fills_claude_settings_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    window_id = uuid4()
    managed = home / ".web-terminal-acp" / "claude-code-homes" / str(window_id)
    managed.mkdir(parents=True)
    (managed / "settings.json").write_text(
        json.dumps({"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "230000"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    window = VirtualWindow(
        id=window_id,
        title="Claude",
        shell_command="claude",
        derived_context=None,
    )
    usage = AgentTokenUsageOut(
        context=AgentTokenUsageCountsOut(input_tokens=112838, output_tokens=863, total_tokens=113701),
        total=AgentTokenUsageCountsOut(input_tokens=112838, output_tokens=863, total_tokens=113701),
        providers=["claude_code"],
        event_count=1,
    )

    patched = token_usage_with_window_model_metadata(
        window,
        usage,
        agent_model_metadata=window_agent_config_model_metadata(window),
    )

    assert patched is not None
    assert patched.auto_compact_token_limit == 230000
    assert patched.providers == ["claude_code"]


def test_token_usage_projection_keeps_window_context_metadata_over_config() -> None:
    window = VirtualWindow(
        title="Claude",
        derived_context={
            "agent_model": {
                "provider": "anthropic_compatible",
                "auto_compact_token_limit": 150000,
            }
        },
    )

    usage = token_usage_with_window_model_metadata(
        window,
        None,
        agent_model_metadata={"provider": "claude_code", "auto_compact_token_limit": 230000},
    )

    assert usage is not None
    assert usage.auto_compact_token_limit == 150000
    assert usage.providers == ["anthropic_compatible"]


def test_token_usage_extracts_nested_claude_usage_and_counts_cache_creation() -> None:
    snapshot = token_usage_from_payload(
        {
            "provider": "claude_code",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "usage": {
                    "input_tokens": 20,
                    "cache_creation_input_tokens": 7,
                    "cache_read_input_tokens": 11,
                    "output_tokens": 5,
                },
            },
        }
    )

    assert snapshot is not None
    assert snapshot.context is not None
    assert snapshot.context.input_tokens == 20
    assert snapshot.context.cached_input_tokens == 11
    assert snapshot.context.cache_creation_input_tokens == 7
    assert snapshot.context.total_tokens == 43
    assert snapshot.total.total_tokens == 43


def test_token_usage_extracts_real_claude_code_message_usage() -> None:
    snapshot = token_usage_from_payload(
        {
            "provider": "claude_code",
            "type": "assistant",
            "message": {
                "id": "resp_1",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "done"}],
                "usage": {
                    "input_tokens": 9370,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 13824,
                    "output_tokens": 19,
                    "server_tool_use": {
                        "web_search_requests": 0,
                        "web_fetch_requests": 0,
                    },
                },
            },
        }
    )

    assert snapshot is not None
    assert snapshot.context is not None
    assert snapshot.context.input_tokens == 9370
    assert snapshot.context.cached_input_tokens == 13824
    assert snapshot.context.output_tokens == 19
    assert snapshot.context.total_tokens == 23213
    assert snapshot.total.total_tokens == 23213


def test_token_usage_extracts_claude_code_otel_token_metric() -> None:
    snapshot = token_usage_from_payload(
        {
            "provider": "claude_code",
            "type": "otel_metric",
            "name": "claude_code.token.usage",
            "attributes": {
                "type": "cacheRead",
                "session.id": "claude-session-1",
                "model": "claude-sonnet-4-6",
            },
            "value": 13824,
        }
    )

    assert snapshot is not None
    assert snapshot.context is not None
    assert snapshot.context.cached_input_tokens == 13824
    assert snapshot.context.total_tokens == 13824
    assert snapshot.total.cached_input_tokens == 13824
    assert snapshot.total.total_tokens == 13824


def test_agent_token_usage_adds_claude_code_otel_metric_increments() -> None:
    events = [
        Event(
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="otel_metric",
            payload_json={
                "provider": "claude_code",
                "type": "otel_metric",
                "name": "claude_code.token.usage",
                "attributes": {"type": token_type, "session.id": "claude-session-1"},
                "value": value,
            },
            fingerprint=f"otel-{token_type}",
            created_at=datetime(2026, 6, 8, 1, index, tzinfo=timezone.utc),
        )
        for index, (token_type, value) in enumerate(
            (
                ("input", 9370),
                ("cacheRead", 13824),
                ("cacheCreation", 7),
                ("output", 19),
            )
        )
    ]

    usage = agent_token_usage_from_events(events)

    assert usage is not None
    assert usage.total.input_tokens == 9370
    assert usage.total.cached_input_tokens == 13824
    assert usage.total.cache_creation_input_tokens == 7
    assert usage.total.output_tokens == 19
    assert usage.total.total_tokens == 23220
    assert usage.providers == ["claude_code"]
    assert usage.event_count == 4


def test_agent_token_usage_uses_grouped_claude_code_otel_metric_as_latest_context() -> None:
    event = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="otel_metric",
        payload_json={
            "provider": "claude_code",
            "type": "otel_metric",
            "name": "claude_code.token.usage",
            "attributes": {"session.id": "claude-session-1", "model": "claude-sonnet-4-6"},
            "usage": {
                "input_tokens": 9370,
                "cache_read_input_tokens": 13824,
                "cache_creation_input_tokens": 7,
                "output_tokens": 19,
                "total_tokens": 23220,
            },
        },
        fingerprint="otel-grouped",
        created_at=datetime(2026, 6, 8, 1, 4, tzinfo=timezone.utc),
    )

    usage = agent_token_usage_from_events([event])

    assert usage is not None
    assert usage.context is not None
    assert usage.context.total_tokens == 23220
    assert usage.total.total_tokens == 23220


def test_agent_token_usage_uses_latest_context_and_adds_incremental_totals() -> None:
    first = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="cursor-session",
        kind="assistant_message",
        payload_json={
            "provider": "cursor_cli",
            "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        },
        fingerprint="usage-1",
        created_at=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
    )
    second = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="cursor-session",
        kind="assistant_message",
        payload_json={
            "provider": "cursor_cli",
            "usage": {"input_tokens": 15, "output_tokens": 6, "total_tokens": 21},
        },
        fingerprint="usage-2",
        created_at=datetime(2026, 6, 8, 1, 1, tzinfo=timezone.utc),
    )

    usage = agent_token_usage_from_events([first, second])

    assert usage is not None
    assert usage.context is not None
    assert usage.context.total_tokens == 21
    assert usage.total.total_tokens == 35
    assert usage.total.input_tokens == 25
    assert usage.total.output_tokens == 10
    assert usage.providers == ["cursor_cli"]
    assert usage.event_count == 2


def test_agent_token_usage_adds_latest_cumulative_snapshot_per_session() -> None:
    first_session_early = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="event_msg",
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
                    "last_token_usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
                },
            },
        },
        fingerprint="codex-usage-1-early",
        created_at=datetime(2026, 6, 8, 2, 0, tzinfo=timezone.utc),
    )
    first_session_late = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="event_msg",
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"input_tokens": 140, "output_tokens": 20, "total_tokens": 160},
                    "last_token_usage": {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50},
                },
            },
        },
        fingerprint="codex-usage-1-late",
        created_at=datetime(2026, 6, 8, 2, 1, tzinfo=timezone.utc),
    )
    second_session = Event(
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-2",
        kind="event_msg",
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"input_tokens": 80, "output_tokens": 12, "total_tokens": 92},
                    "last_token_usage": {"input_tokens": 80, "output_tokens": 12, "total_tokens": 92},
                },
            },
        },
        fingerprint="codex-usage-2",
        created_at=datetime(2026, 6, 8, 2, 2, tzinfo=timezone.utc),
    )

    usage = agent_token_usage_from_events([first_session_early, first_session_late, second_session])

    assert usage is not None
    assert usage.context is not None
    assert usage.context.total_tokens == 92
    assert usage.total.total_tokens == 252
    assert usage.total.input_tokens == 220
    assert usage.total.output_tokens == 32
    assert usage.event_count == 3


async def test_load_agent_token_usage_for_window_scans_real_claude_kind(db_session) -> None:
    client_id = uuid4()
    window_id = uuid4()
    event = Event(
        client_id=client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="assistant",
        virtual_window_id=window_id,
        payload_json={
            "provider": "claude_code",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "done"}],
                "usage": {
                    "input_tokens": 200,
                    "cache_read_input_tokens": 50,
                    "output_tokens": 20,
                },
            },
        },
        fingerprint="claude-usage-real-kind",
        created_at=datetime(2026, 6, 8, 3, 0, tzinfo=timezone.utc),
    )
    db_session.add(event)
    await db_session.commit()

    usage = await load_agent_token_usage_for_window(
        db_session,
        client_id=client_id,
        window_id=window_id,
    )

    assert usage is not None
    assert usage.context is not None
    assert usage.context.total_tokens == 270
    assert usage.total.total_tokens == 270
    assert usage.providers == ["claude_code"]
    assert usage.event_count == 1
