import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import Event, SummaryJob, VirtualWindow, WindowStatus
from app.services.search_index import TERMINAL_INDEX
from app.services.terminal_output_recorder import record_terminal_input_command, record_terminal_output_chunk
from app.services import terminal_output_recorder


def _command_marker(window_id, payload: dict) -> bytes:
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return f"\x1b]777;web-terminal-command;window_id={window_id};payload={encoded}\x07".encode("ascii")


class FakeElasticsearch:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.indexed_documents = []

    async def index(self, **kwargs):
        if self.fail:
            raise RuntimeError("Elasticsearch unavailable")
        self.indexed_documents.append(kwargs)
        return {"result": "created"}


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_record_terminal_output_tracks_activity_and_indexes_without_event_rows(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()
    es_client = FakeElasticsearch()

    recorded = await record_terminal_output_chunk(db_session, client_id, window.id, b"hello terminal\n", es_client)

    rows = (await db_session.execute(select(Event))).scalars().all()
    assert recorded is True
    assert rows == []
    await db_session.refresh(window)
    assert window.terminal_last_output_at is not None
    assert es_client.indexed_documents == [
        {
            "index": TERMINAL_INDEX,
            "id": es_client.indexed_documents[0]["id"],
            "document": {
                "client_id": str(client_id),
                "virtual_window_id": str(window.id),
                "text": "hello terminal\n",
                "source_event_ids": [],
            },
        }
    ]
    assert str(es_client.indexed_documents[0]["id"]).startswith(f"terminal-chunk:{window.id}:")


@pytest.mark.asyncio
async def test_record_terminal_output_keeps_activity_when_indexing_fails(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()

    recorded = await record_terminal_output_chunk(
        db_session,
        client_id,
        window.id,
        b"index later",
        FakeElasticsearch(fail=True),
    )

    rows = (await db_session.execute(select(Event))).scalars().all()
    assert recorded is True
    assert rows == []
    await db_session.refresh(window)
    assert window.terminal_last_output_at is not None


@pytest.mark.asyncio
async def test_record_terminal_output_ignores_empty_decoded_chunks(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()

    recorded = await record_terminal_output_chunk(db_session, client_id, window.id, b"", FakeElasticsearch())

    rows = (await db_session.execute(select(Event))).scalars().all()
    assert recorded is False
    assert rows == []


@pytest.mark.asyncio
async def test_agent_tui_terminal_output_does_not_enqueue_summary_job(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()

    await record_terminal_input_command(
        db_session,
        client_id,
        window.id,
        "codex",
        "bash",
        "/workspace/project",
        datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
        1,
    )
    await record_terminal_output_chunk(db_session, client_id, window.id, b"codex tui refresh\n")

    jobs = (await db_session.execute(select(SummaryJob))).scalars().all()
    assert jobs == []


@pytest.mark.asyncio
async def test_auto_resume_command_markers_are_not_persisted(db_session):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()

    marker = _command_marker(
        window.id,
        {
            "phase": "started",
            "command": "WEB_TERMINAL_AUTO_RESUME=1 claude --resume claude-session",
            "shell": "zsh",
            "cwd": "/workspace/project",
            "captured_at": "2026-05-21T12:00:00+00:00",
            "sequence": 7,
        },
    )
    event = await record_terminal_output_chunk(db_session, client_id, window.id, marker)

    rows = (await db_session.execute(select(Event))).scalars().all()
    assert event is False
    assert rows == []


@pytest.mark.asyncio
async def test_record_terminal_output_throttles_postgres_activity_touches(db_session, monkeypatch):
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.commit()
    terminal_output_recorder._terminal_output_activity_touched_at.clear()
    monotonic = iter([100.0, 100.25])
    commits = 0
    original_commit = db_session.commit

    async def counted_commit():
        nonlocal commits
        commits += 1
        await original_commit()

    monkeypatch.setattr(terminal_output_recorder, "monotonic", lambda: next(monotonic))
    monkeypatch.setattr(db_session, "commit", counted_commit)

    assert await record_terminal_output_chunk(db_session, client_id, window.id, b"one") is True
    assert await record_terminal_output_chunk(db_session, client_id, window.id, b"two") is True

    rows = (await db_session.execute(select(Event))).scalars().all()
    assert rows == []
    assert commits == 1
