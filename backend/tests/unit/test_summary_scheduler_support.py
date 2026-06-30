from datetime import datetime, timedelta, timezone

from uuid import uuid4

import pytest

from sqlalchemy import event, select

from sqlalchemy.exc import IntegrityError

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings

from app.model_base import Base

from app.models import Event, EventSourceType, SummaryJob, SummaryJobStatus, VirtualWindow, WindowStatus

from app.repositories.summary_jobs import claim_next_summary_job, enqueue_summary_job

from app.services.summary_scheduler import (
    AGENT_IDLE_REASON,
    PROJECT_TODO_DISPATCH_REASON,
    schedule_summary_after_agent_activity,
    schedule_summary_after_project_todo_dispatch,
    schedule_summary_after_terminal_input,
)

from app.services.terminal_output_recorder import record_terminal_input_command

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def _disable_completion_verification(monkeypatch):
    """Existing summary-scheduler unit tests pre-date completion verification.
    Disable it so they continue to assert the legacy direct-upgrade behavior."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "project_todo_completion_verification_enabled",
        False,
    )

@pytest.fixture
async def counted_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def record_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session, statements

    await engine.dispose()

async def create_window(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    return window

async def add_input_event(db_session, window, captured_at, sequence):
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.terminal,
        source_id=str(window.id),
        kind="terminal_input_command",
        virtual_window_id=window.id,
        payload_json={
            "command": f"echo {sequence}",
            "shell": "bash",
            "captured_at": captured_at.isoformat(),
            "sequence": sequence,
        },
        fingerprint=f"terminal_input_command:{window.id}:{sequence}",
        created_at=captured_at,
    )
    db_session.add(event)
    await db_session.flush()
    return event

async def add_shell_input(db_session, window, captured_at, sequence):
    return await add_input_event(db_session, window, captured_at, sequence)

async def add_agent_event(db_session, window, created_at, *, fingerprint: str, kind: str = "assistant_message"):
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="agent-session-1",
        kind=kind,
        virtual_window_id=window.id,
        payload_json={
            "provider": "cursor_cli",
            "role": "user" if kind == "user_message" else "assistant",
            "content": "please summarize this work" if kind == "user_message" else "working",
        },
        fingerprint=fingerprint,
        created_at=created_at,
    )
    db_session.add(event)
    await db_session.flush()
    return event

async def add_agent_command_input(db_session, window, captured_at, sequence):
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.terminal,
        source_id=str(window.id),
        kind="terminal_input_command",
        virtual_window_id=window.id,
        payload_json={
            "command": "codex",
            "shell": "bash",
            "captured_at": captured_at.isoformat(),
            "sequence": sequence,
        },
        fingerprint=f"terminal_input_command:{window.id}:agent-{sequence}",
        created_at=captured_at,
    )
    db_session.add(event)
    await db_session.flush()
    return event

__all__ = [name for name in globals() if not name.startswith("__")]
