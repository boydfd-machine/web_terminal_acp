from contextlib import asynccontextmanager
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.model_base import Base
from app.models import (
    AiSession,
    Event,
    EventSourceType,
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoStatus,
    SummaryJob,
    TerminalArtifact,
    VirtualWindow,
    WindowStatus,
)
from app.repositories.clients import create_client, ensure_local_client
from app.services.ingest.claude_watcher import (
    index_claude_events,
    ingest_claude_jsonl_file,
    initial_jsonl_offsets,
    iter_jsonl_files,
    poll_claude_jsonl_directory_once,
    read_new_jsonl_events,
)
from app.services.ingest.normalizers import normalize_claude_jsonl
from app.services.search_index import AI_EVENTS_INDEX


class FakeElasticsearch:
    def __init__(self):
        self.indexed_documents = []

    async def index(self, **kwargs):
        self.indexed_documents.append(kwargs)
        return {"result": "created"}


class FailingElasticsearch:
    async def index(self, **kwargs):
        raise RuntimeError("search index unavailable")


class FakeUiEventHub:
    def __init__(self):
        self.invalidations = []

    async def publish_invalidation(self, resources, **kwargs):
        self.invalidations.append((list(resources), kwargs))


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


def write_jsonl(path, *objects):
    path.write_text("".join(json.dumps(obj, ensure_ascii=False) + "\n" for obj in objects), encoding="utf-8")

@pytest.mark.asyncio
async def test_poll_claude_jsonl_directory_once_dispatches_requested_project_todo_artifacts(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", False)
    import app.services.ingest.claude_watcher as claude_watcher

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session_factory():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    async with AsyncSession(engine, expire_on_commit=False) as session:
        client = await ensure_local_client(session)
        window = VirtualWindow(
            id=uuid4(),
            client_id=client.id,
            title="Claude todo",
            cwd="/workspace/project",
            shell_command="claude",
            status=WindowStatus.active,
        )
        todo = ProjectTodo(
            id=uuid4(),
            client_id=client.id,
            project_path="/workspace/project",
            title="Generate artifact after Claude completion",
            status=ProjectTodoStatus.dispatched,
            assigned_window_id=window.id,
            artifact_kinds_json=["agent_trace_graph"],
        )
        session.add_all([window, todo])
        await session.commit()

    scheduled = []

    def fake_schedule_project_todo_artifact_generations(generations, runtime=None):
        scheduled.extend(generations)

    monkeypatch.setattr(
        claude_watcher,
        "schedule_project_todo_artifact_generations",
        fake_schedule_project_todo_artifact_generations,
    )

    root = tmp_path / "claude"
    root.mkdir()
    path = root / "session.jsonl"
    write_jsonl(
        path,
        {
            "type": "assistant",
            "sessionId": "claude-session-artifact",
            "virtual_window_id": str(window.id),
            "message": {
                "role": "assistant",
                "content": "done",
                "stop_reason": "end_turn",
            },
            "timestamp": "2026-06-07T12:00:00+00:00",
        },
    )

    await poll_claude_jsonl_directory_once(session_factory, root, {})

    assert len(scheduled) == 1
    assert scheduled[0].client_id == window.client_id
    assert scheduled[0].window_id == window.id
    async with AsyncSession(engine, expire_on_commit=False) as session:
        [link] = list((await session.execute(select(ProjectTodoArtifact))).scalars())
        artifact = await session.get(TerminalArtifact, link.terminal_artifact_id)
    assert artifact is not None
    assert scheduled[0].artifact_id == artifact.id
    assert artifact.metadata_json["dispatch_attempted_at"]

    await engine.dispose()

@pytest.mark.asyncio
async def test_claude_jsonl_ingest_invalidation_does_not_expire_tree_cache(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session_factory():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    root = tmp_path / "claude"
    root.mkdir()
    path = root / "session.jsonl"
    write_jsonl(path, {"type": "user", "message": {"content": "hello"}, "sessionId": "s1"})
    ui_event_hub = FakeUiEventHub()

    await poll_claude_jsonl_directory_once(
        session_factory,
        root,
        {},
        ui_event_hub=ui_event_hub,
    )

    assert ui_event_hub.invalidations == [
        (
            ["agent_record", "window", "search"],
            {
                "client_id": next(
                    kwargs["client_id"] for _resources, kwargs in ui_event_hub.invalidations
                ),
                "reason": "claude_jsonl_ingested",
            },
        )
    ]

    await engine.dispose()

def test_long_path_fingerprints_remain_within_event_fingerprint_limit(tmp_path):
    long_root = tmp_path / ("nested" * 30)
    long_root.mkdir()
    source_path = str(long_root / "session.jsonl")
    raw = {"type": "user", "message": {"content": "hello"}}

    event = normalize_claude_jsonl(raw, source_path=source_path, offset=99)

    assert len(event.fingerprint) <= Event.__table__.c.fingerprint.type.length
