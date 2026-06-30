from datetime import datetime, timedelta, timezone

from uuid import uuid4

import pytest

from sqlalchemy import event

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base

from app.models import Event, EventSourceType, VirtualWindow, WindowStatus

from app.services import terminal_work_status

from app.services.terminal_work_status import (
    load_tree_window_activity,
    load_last_agent_task_completed_at_by_window,
    load_work_statuses,
    load_work_status,
    work_status_from_activity,
)

def codex_completion_payload(
    *, event_type: str = "task_completed", timestamp: datetime | None = None
) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "event_msg",
        "payload": {"type": event_type},
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def codex_message_payload(text: str, *, timestamp: datetime | None = None) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        },
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def codex_user_message_payload(text: str, *, timestamp: datetime | None = None) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def claude_completion_payload() -> dict:
    return {
        "provider": "claude_code",
        "type": "assistant",
        "message": {
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "done"}],
        },
    }

def claude_turn_duration_payload(*, timestamp: datetime | None = None) -> dict:
    payload = {
        "provider": "claude_code",
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": 166049,
        "messageCount": 37,
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def claude_local_command_payload(text: str = "<bash-stdout>done</bash-stdout>") -> dict:
    return {
        "provider": "claude_code",
        "type": "user",
        "message": {
            "role": "user",
            "content": text,
        },
        "isMeta": True,
    }

def claude_metadata_payload(payload_type: str) -> dict:
    return {
        "provider": "claude_code",
        "type": payload_type,
        "content": "metadata",
    }

def cursor_completion_payload(text: str = "done") -> dict:
    return {
        "provider": "cursor_cli",
        "role": "assistant",
        "text": text,
    }

def antigravity_completion_payload(text: str = "done") -> dict:
    return {
        "provider": "antigravity_cli",
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "status": "DONE",
        "content": text,
    }

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

__all__ = [name for name in globals() if not name.startswith("__")]
