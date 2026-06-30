import json

from datetime import datetime, timedelta, timezone

from uuid import uuid4

import pytest

from sqlalchemy import event, select

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings

from app.model_base import Base

from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    ClientStatus,
    Event,
    EventSourceType,
    ProjectTodo,
    ProjectTodoStatus,
    VirtualWindow,
)

from app.repositories.clients import ensure_local_client, hash_client_token

from app.repositories.folders import get_or_create_folder_by_path

from app.repositories.summary_jobs import collect_summary_context

from app.contexts.windows.infrastructure.repository import create_window

@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        await engine.dispose()

@pytest.fixture
async def counted_session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/counted.db")
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def record_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield Session, statements
    finally:
        await engine.dispose()

async def create_local_window(session):
    client = await ensure_local_client(session)
    return await create_window(session, client.id, cwd="/workspace/project", shell_command="/bin/bash")

def command_event(window: VirtualWindow, sequence: int, command: str, captured_at: datetime) -> Event:
    return Event(
        client_id=window.client_id,
        source_type=EventSourceType.terminal,
        source_id=f"terminal-command-{sequence}",
        kind="terminal_input_command",
        virtual_window_id=window.id,
        payload_json={
            "sequence": sequence,
            "command": command,
            "shell": "/bin/bash",
            "cwd": f"/workspace/project-{sequence}",
            "captured_at": captured_at.isoformat(),
        },
        fingerprint=f"terminal-command-{sequence}",
        created_at=captured_at,
    )

def output_event(window: VirtualWindow, text: str, created_at: datetime) -> Event:
    return Event(
        client_id=window.client_id,
        source_type=EventSourceType.terminal,
        source_id="terminal-output",
        kind="terminal_output",
        virtual_window_id=window.id,
        payload_json={"text": text},
        fingerprint="terminal-output",
        created_at=created_at,
    )

__all__ = [name for name in globals() if not name.startswith("__")]
