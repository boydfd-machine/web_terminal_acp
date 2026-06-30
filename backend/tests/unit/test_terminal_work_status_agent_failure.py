from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import Event, EventSourceType, VirtualWindow, WindowStatus
from app.services.terminal_work_status import load_tree_window_activity
from tests.unit.test_terminal_work_status_support import codex_completion_payload


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_load_tree_window_activity_reports_failure_for_stream_disconnect(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(minutes=2)
    failed_at = now - timedelta(seconds=10)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'fail'", "sequence": 3},
            fingerprint="terminal-input-codex-stream-disconnect",
            created_at=completed_at - timedelta(seconds=10),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="event_msg",
            virtual_window_id=window.id,
            payload_json=codex_completion_payload(timestamp=completed_at),
            fingerprint="codex-completed-before-stream-disconnect",
            created_at=completed_at,
        ),
        Event(
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
            fingerprint="codex-stream-disconnect-failed",
            created_at=failed_at,
        ),
    ])
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "FAILED"
    assert window.id not in activity.last_agent_task_completed_at
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FAILED"
    assert task_status.occurred_at == failed_at


@pytest.mark.asyncio
async def test_load_tree_window_activity_reports_failure_for_nonzero_agent_exit(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    command_at = now - timedelta(seconds=20)
    failed_at = now - timedelta(seconds=5)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'fail'", "sequence": 4},
            fingerprint="terminal-input-codex-nonzero",
            created_at=command_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 4, "exit_status": 1},
            fingerprint="terminal-finished-codex-nonzero",
            created_at=failed_at,
        ),
    ])
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "FAILED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FAILED"
    assert task_status.occurred_at == failed_at
