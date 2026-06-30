from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import (
    Client,
    ClientRuntime,
    ClientStatus,
    Event,
    EventSourceType,
    Folder,
    TerminalNotificationState,
    VirtualWindow,
    WindowStatus,
)
from app.services.terminal_notifications import clear_terminal_notifications, list_terminal_notifications


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
async def test_clear_terminal_notifications_batches_state_updates(counted_db_session) -> None:
    session, statements = counted_db_session
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    folder_id = uuid4()
    session.add(
        Client(
            id=client_id,
            name="remote",
            status=ClientStatus.ONLINE,
            token_hash=f"sha256:{'1' * 64}",
            runtime=ClientRuntime.remote,
        )
    )
    session.add(Folder(id=folder_id, client_id=client_id, name="Project", path="/tmp/project"))
    windows = [
        VirtualWindow(
            id=uuid4(),
            client_id=client_id,
            folder_id=folder_id,
            title=f"Terminal {index}",
            status=WindowStatus.active,
            agent_activity_latest_at=now - timedelta(minutes=index + 1),
            agent_activity_latest_completed_at=now - timedelta(minutes=index + 1),
        )
        for index in range(3)
    ]
    session.add_all(windows)
    await session.flush()
    statements.clear()

    await clear_terminal_notifications(session, client_id)

    notification_state_selects = [
        statement
        for statement in statements
        if "FROM terminal_notification_states" in statement
        and statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(notification_state_selects) == 2

    states = list(
        await session.scalars(
            select(TerminalNotificationState).where(
                TerminalNotificationState.client_id == client_id
            )
        )
    )
    assert len(states) == len(windows)
    assert all(state.read_at is not None and state.dismissed_at is not None for state in states)


@pytest.mark.asyncio
async def test_list_terminal_notifications_includes_failed_agent_status(counted_db_session) -> None:
    session, _statements = counted_db_session
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    folder_id = uuid4()
    session.add(
        Client(
            id=client_id,
            name="remote",
            status=ClientStatus.ONLINE,
            token_hash=f"sha256:{'1' * 64}",
            runtime=ClientRuntime.remote,
        )
    )
    session.add(Folder(id=folder_id, client_id=client_id, name="Project", path="/tmp/project"))
    failed_at = now - timedelta(seconds=20)
    failure_event_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        folder_id=folder_id,
        title="Failing Agent",
        status=WindowStatus.active,
        agent_activity_latest_at=failed_at,
        agent_activity_latest_event_id=failure_event_id,
    )
    session.add_all(
        [
            window,
            Event(
                id=failure_event_id,
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "stream disconnected before completion: stream closed before response.completed",
                    },
                },
                fingerprint="codex-failed-terminal-notification",
                created_at=failed_at,
            ),
        ]
    )
    await session.flush()

    notifications = await list_terminal_notifications(session, client_id)

    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.window_id == window.id
    assert notification.status == "FAILED"
    assert notification.completed_at == failed_at
    assert notification.read is False
