from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.activity.application.terminal_work_status.projection_status import load_projected_work_statuses
from app.model_base import Base
from app.models import Event, EventSourceType, VirtualWindow, WindowStatus
from tests.unit.test_terminal_work_status_support import claude_completion_payload


@pytest.fixture
async def counted_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def count_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session, statements

    await engine.dispose()


@pytest.mark.asyncio
async def test_projected_work_status_uses_window_projection_without_event_scan(
    counted_db_session,
    monkeypatch,
) -> None:
    session, statements = counted_db_session
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Agent",
        status=WindowStatus.active,
        agent_activity_latest_at=now - timedelta(seconds=5),
    )
    session.add(window)
    await session.flush()
    monkeypatch.setattr(
        "app.contexts.activity.application.terminal_work_status.projection_status._dialect_name",
        lambda _session: "postgresql",
    )
    statements.clear()

    statuses = await load_projected_work_statuses(session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "WORKING"
    assert not [statement for statement in statements if "FROM events" in statement]


@pytest.mark.asyncio
async def test_projected_work_status_applies_manual_override(
    counted_db_session,
    monkeypatch,
) -> None:
    session, _statements = counted_db_session
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Agent",
        status=WindowStatus.active,
        agent_activity_latest_at=now - timedelta(seconds=5),
        manual_work_status_state="FINISHED",
        manual_work_status_updated_at=now,
    )
    session.add(window)
    await session.flush()
    monkeypatch.setattr(
        "app.contexts.activity.application.terminal_work_status.projection_status._dialect_name",
        lambda _session: "postgresql",
    )

    statuses = await load_projected_work_statuses(session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "FINISHED"
    assert statuses[window.id].source == "manual"


@pytest.mark.asyncio
async def test_projected_work_status_does_not_treat_user_input_as_agent_output(
    counted_db_session,
    monkeypatch,
) -> None:
    session, statements = counted_db_session
    now = datetime(2026, 6, 8, 12, 20, tzinfo=timezone.utc)
    client_id = uuid4()
    input_at = now - timedelta(minutes=20)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Claude idle prompt",
        status=WindowStatus.active,
        agent_activity_latest_at=input_at,
        agent_activity_latest_user_input_at=input_at,
    )
    session.add(window)
    await session.flush()
    monkeypatch.setattr(
        "app.contexts.activity.application.terminal_work_status.projection_status._dialect_name",
        lambda _session: "postgresql",
    )
    statements.clear()

    statuses = await load_projected_work_statuses(session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "LONG_IDLE"
    assert not [statement for statement in statements if "FROM events" in statement]


@pytest.mark.asyncio
async def test_projected_work_status_keeps_pending_subagent_working_after_user_input(
    counted_db_session,
    monkeypatch,
) -> None:
    session, statements = counted_db_session
    now = datetime(2026, 6, 8, 12, 20, tzinfo=timezone.utc)
    client_id = uuid4()
    input_at = now - timedelta(minutes=20)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Claude waiting for subagent",
        status=WindowStatus.active,
        agent_activity_latest_at=input_at,
        agent_activity_latest_user_input_at=input_at,
        agent_activity_pending_subagent_count=1,
    )
    session.add(window)
    await session.flush()
    monkeypatch.setattr(
        "app.contexts.activity.application.terminal_work_status.projection_status._dialect_name",
        lambda _session: "postgresql",
    )
    statements.clear()

    statuses = await load_projected_work_statuses(session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "WORKING"
    assert not [statement for statement in statements if "FROM events" in statement]


@pytest.mark.asyncio
async def test_projected_work_status_keeps_claude_finished_after_token_metric(
    counted_db_session,
    monkeypatch,
) -> None:
    session, statements = counted_db_session
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    completed_at = now - timedelta(seconds=30)
    metric_at = now - timedelta(seconds=5)
    metric_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Claude",
        status=WindowStatus.active,
        agent_activity_latest_at=metric_at,
        agent_activity_latest_event_id=metric_id,
        agent_activity_latest_completed_at=completed_at,
    )
    session.add_all(
        [
            window,
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json=claude_completion_payload(),
                fingerprint="projected-claude-completed-before-token-metric",
                created_at=completed_at,
            ),
            Event(
                id=metric_id,
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="otel://claude-code/metrics",
                kind="otel_metric",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "claude_code",
                    "type": "otel_metric",
                    "name": "claude_code.token.usage",
                    "attributes": {"session.id": "claude-session-1"},
                    "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
                },
                fingerprint="projected-claude-token-metric-after-completion",
                created_at=metric_at,
            ),
        ]
    )
    await session.flush()
    monkeypatch.setattr(
        "app.contexts.activity.application.terminal_work_status.projection_status._dialect_name",
        lambda _session: "postgresql",
    )
    statements.clear()

    statuses = await load_projected_work_statuses(session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "FINISHED"
    assert statuses[window.id].last_activity_at == completed_at
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]
