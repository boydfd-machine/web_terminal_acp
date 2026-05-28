from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import Event, EventSourceType, VirtualWindow, WindowStatus
from app.services.terminal_work_status import (
    load_last_agent_task_completed_at_by_window,
    load_work_statuses,
    load_work_status,
    work_status_from_activity,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


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


def test_work_status_from_activity_returns_long_idle_after_recent_window() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=6),
        last_working_activity_at=now - timedelta(minutes=6),
    )

    assert status.state == "LONG_IDLE"
    assert status.label == "长时间没有工作了"
    assert status.color == "gray"


def test_work_status_from_activity_prefers_working_for_recent_agent_activity() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(seconds=20),
        last_working_activity_at=now - timedelta(seconds=20),
    )

    assert status.state == "WORKING"
    assert status.label == "正在工作中"
    assert status.color == "orange"


def test_work_status_from_activity_returns_recent_active_for_stale_agent_activity() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=2),
        last_working_activity_at=now - timedelta(minutes=2),
    )

    assert status.state == "RECENT_ACTIVE"


def test_work_status_from_activity_returns_recent_active_for_recent_input_only() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=2),
        last_working_activity_at=None,
    )

    assert status.state == "RECENT_ACTIVE"
    assert status.label == "最近刚活跃过"
    assert status.color == "green"


@pytest.mark.asyncio
async def test_load_work_statuses_batches_latest_activity_queries(counted_db_session) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    windows = [
        VirtualWindow(id=uuid4(), client_id=client_id, title=f"Terminal {index}", status=WindowStatus.active)
        for index in range(3)
    ]
    db_session.add_all(windows)
    await db_session.flush()
    windows[0].terminal_last_output_at = now - timedelta(seconds=15)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="assistant_message",
                virtual_window_id=windows[1].id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint="agent-tool-record-latest",
                created_at=now - timedelta(seconds=10),
            ),
        ]
    )
    await db_session.flush()
    statements.clear()

    statuses = await load_work_statuses(
        db_session,
        client_id,
        [window.id for window in windows],
        now=now,
    )

    assert statuses[windows[0].id].state == "RECENT_ACTIVE"
    assert statuses[windows[1].id].state == "WORKING"
    latest_activity_queries = [
        statement
        for statement in statements
        if "events.created_at" in statement
        and "virtual_windows" in statement
        and "SELECT virtual_windows.id" in statement
    ]
    assert len(latest_activity_queries) <= 2


@pytest.mark.asyncio
async def test_load_work_status_treats_agent_tool_records_as_working_activity(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="cursor-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={"provider": "cursor_cli", "role": "assistant", "content": "working"},
            fingerprint="cursor-agent-work-status",
            created_at=now - timedelta(seconds=20),
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"
    assert status.last_activity_at == now - timedelta(seconds=20)
    assert status.last_working_activity_at == now - timedelta(seconds=20)


@pytest.mark.asyncio
async def test_load_work_status_uses_lightweight_terminal_output_activity(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.terminal_last_output_at = now - timedelta(seconds=5)
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"


@pytest.mark.asyncio
async def test_load_work_status_returns_working_for_in_progress_agent_command(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'fix tests'", "sequence": 7},
            fingerprint="terminal-input-codex",
            created_at=now - timedelta(seconds=30),
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"


@pytest.mark.asyncio
async def test_load_work_status_returns_idle_for_stale_in_progress_agent_command_without_activity(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'fix tests'", "sequence": 7},
                fingerprint="terminal-input-codex",
                created_at=now - timedelta(minutes=5),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint="codex-agent-stale-work-status",
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_activity_at == now - timedelta(minutes=2)
    assert status.last_working_activity_at == now - timedelta(minutes=2)


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_uses_latest_agent_result_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    result_at = now - timedelta(seconds=30)
    finished_at = now - timedelta(seconds=5)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "pwd", "sequence": 1},
            fingerprint="terminal-finished-shell",
            created_at=now - timedelta(seconds=10),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'done'", "sequence": 2},
            fingerprint="terminal-input-codex",
            created_at=result_at - timedelta(seconds=5),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2},
            fingerprint="terminal-finished-codex",
            created_at=finished_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="response_item",
            virtual_window_id=window.id,
            payload_json={
                "provider": "codex",
                "raw_type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "done"}],
                },
            },
            fingerprint="codex-agent-result",
            created_at=result_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == finished_at


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_waits_until_agent_result_is_idle(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    result_at = now - timedelta(seconds=10)
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="response_item",
            virtual_window_id=window.id,
            payload_json={
                "provider": "codex",
                "raw_type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "still working"}],
                },
            },
            fingerprint="codex-agent-result-still-working",
            created_at=result_at,
        )
    )
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    assert latest == {}


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_ignores_agent_command_without_result_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=30)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'done'", "sequence": 2},
            fingerprint="terminal-input-codex",
            created_at=completed_at - timedelta(seconds=5),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2},
            fingerprint="terminal-finished-codex",
            created_at=completed_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    assert latest == {}


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_does_not_attach_old_result_to_new_empty_agent_exit(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    old_result_at = now - timedelta(minutes=10)
    old_finished_at = old_result_at + timedelta(seconds=20)
    new_started_at = now - timedelta(minutes=2)
    new_finished_at = now - timedelta(minutes=1)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude -p 'fix'", "sequence": 1},
            fingerprint="terminal-input-claude-old",
            created_at=old_result_at - timedelta(seconds=10),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={
                "provider": "claude_code",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "old result"}],
                },
            },
            fingerprint="claude-agent-result-old",
            created_at=old_result_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 1, "exit_status": 0},
            fingerprint="terminal-finished-claude-old",
            created_at=old_finished_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude", "sequence": 2},
            fingerprint="terminal-input-claude-new",
            created_at=new_started_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2, "exit_status": 0},
            fingerprint="terminal-finished-claude-new",
            created_at=new_finished_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == old_finished_at


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_prefers_newer_agent_result_output(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    older_result_at = now - timedelta(minutes=2)
    newer_result_at = now - timedelta(seconds=30)
    newer_finished_at = now - timedelta(seconds=5)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'newer done'", "sequence": 2},
            fingerprint="terminal-input-codex-newer",
            created_at=newer_result_at - timedelta(seconds=5),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2},
            fingerprint="terminal-finished-codex-newer",
            created_at=newer_finished_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={
                "provider": "claude_code",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "old result"}],
                },
            },
            fingerprint="claude-agent-result-older",
            created_at=older_result_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="response_item",
            virtual_window_id=window.id,
            payload_json={
                "provider": "codex",
                "raw_type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "newer result"}],
                },
            },
            fingerprint="codex-agent-result-newer",
            created_at=newer_result_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == newer_finished_at


@pytest.mark.asyncio
async def test_load_last_agent_task_completed_ignores_idle_agent_activity_without_result(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    working_at = now - timedelta(seconds=120)
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={"provider": "claude_code", "role": "assistant", "content": "working"},
            fingerprint="claude-agent-idle-work",
            created_at=working_at,
        )
    )
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    assert latest == {}
