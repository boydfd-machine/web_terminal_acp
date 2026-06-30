from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.client_agent.ai_events import managed_event_from_payload
from app.db import Base
from app.models import AiSession, Client, ClientRuntime, ClientStatus, Event, EventSourceType, SummaryJob, VirtualWindow, WindowStatus
from app.repositories.clients import hash_client_token
from app.services import agent_event_ingest
from app.contexts.activity.application.agent_event_processor import process_managed_agent_event
from app.services.agent_event_ingest import persist_managed_agent_event
from app.services.ingest.codex_receiver import receive_managed_codex_trace


class FakeElasticsearch:
    def __init__(self) -> None:
        self.indexed_documents = []

    async def index(self, **kwargs):
        self.indexed_documents.append(kwargs)
        return {"result": "created"}


class CaptureUiEventHub:
    def __init__(self) -> None:
        self.invalidations = []

    async def publish_invalidation(
        self,
        resources,
        *,
        client_id=None,
        window_id=None,
        reason=None,
    ) -> None:
        self.invalidations.append(
            {
                "resources": list(resources),
                "client_id": client_id,
                "window_id": window_id,
                "reason": reason,
            }
        )


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


async def create_client_and_window(db_session, *, cwd="/workspace/window"):
    client = Client(
        id=uuid4(),
        name="remote",
        status=ClientStatus.ONLINE,
        token_hash=hash_client_token("token"),
        runtime=ClientRuntime.remote,
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Terminal",
        status=WindowStatus.active,
        cwd=cwd,
        shell_command="/bin/bash",
    )
    db_session.add_all([client, window])
    await db_session.flush()
    return client, window

@pytest.mark.asyncio
async def test_persist_managed_cursor_event_links_session_window_project_without_indexing(db_session):
    client, window = await create_client_and_window(db_session)
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-1",
        "blob_id": "blob-1",
        "role": "assistant",
        "text": "managed cursor hello",
        "WEB_TERMINAL_PROJECT_PATH": "/workspace/project",
    }
    event = managed_event_from_payload(
        client.id,
        window.id,
        "cursor_cli",
        payload,
        source_path="/home/user/.cursor/store.db",
        cursor="root-1",
    )
    assert event is not None
    es_client = FakeElasticsearch()

    row = await persist_managed_agent_event(db_session, event, es_client=es_client)

    ai_session = await db_session.get(AiSession, row.ai_session_id)
    summary_jobs = (await db_session.execute(select(SummaryJob))).scalars().all()
    assert row.client_id == client.id
    assert row.virtual_window_id == window.id
    assert row.source_type is EventSourceType.agent_tool_record
    assert row.source_id == "cursor-agent-1"
    assert row.indexed_at is None
    assert ai_session is not None
    assert ai_session.provider == "cursor_cli"
    assert ai_session.source_id == "cursor-agent-1"
    assert ai_session.source_path == "/home/user/.cursor/store.db"
    assert ai_session.project_path == "/workspace/project"
    assert ai_session.virtual_window_id == window.id
    assert summary_jobs[0].virtual_window_id == window.id
    assert es_client.indexed_documents == []

@pytest.mark.asyncio
async def test_persist_managed_agent_event_skips_summary_for_ephemeral_window(db_session):
    client, window = await create_client_and_window(db_session)
    window.derived_mode = "ephemeral"
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-ephemeral",
        "blob_id": "blob-ephemeral-1",
        "role": "user",
        "text": "artifact-internal prompt",
    }
    event = managed_event_from_payload(client.id, window.id, "cursor_cli", payload)
    assert event is not None

    row = await persist_managed_agent_event(db_session, event)

    ai_session = await db_session.get(AiSession, row.ai_session_id)
    assert row.virtual_window_id == window.id
    assert ai_session is not None
    assert ai_session.virtual_window_id == window.id
    assert (await db_session.execute(select(SummaryJob))).scalars().all() == []

@pytest.mark.asyncio
async def test_persist_ephemeral_agent_event_does_not_reassign_main_window_session(db_session):
    client, main_window = await create_client_and_window(db_session)
    artifact_window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Artifact terminal",
        status=WindowStatus.active,
        cwd=main_window.cwd,
        shell_command="codex",
        parent_window_id=main_window.id,
        root_window_id=main_window.id,
        derived_mode="ephemeral",
    )
    main_ai_session = AiSession(
        client_id=client.id,
        provider="codex",
        source_id="codex-main-session",
        source_path="/home/user/.web-terminal-acp/codex-homes/main/session.jsonl",
        virtual_window_id=main_window.id,
    )
    db_session.add_all([artifact_window, main_ai_session])
    await db_session.flush()

    payload = {
        "trace_id": "codex-main-session",
        "id": "codex-main-session:0",
        "name": "response_item",
        "raw_type": "response_item",
        "client_id": str(client.id),
        "virtual_window_id": str(artifact_window.id),
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "artifact-only"}],
        },
    }
    event = managed_event_from_payload(client.id, artifact_window.id, "codex", payload)
    assert event is not None

    row = await persist_managed_agent_event(db_session, event)

    artifact_ai_session = await db_session.get(AiSession, row.ai_session_id)
    await db_session.refresh(main_ai_session)
    assert main_ai_session.virtual_window_id == main_window.id
    assert artifact_ai_session is not None
    assert artifact_ai_session.id != main_ai_session.id
    assert artifact_ai_session.virtual_window_id == artifact_window.id
    assert artifact_ai_session.source_id == main_ai_session.source_id
    assert row.virtual_window_id == artifact_window.id
    assert row.source_id == main_ai_session.source_id

@pytest.mark.asyncio
async def test_persist_managed_user_event_schedules_summary_even_after_recent_terminal_activity(db_session):
    client, window = await create_client_and_window(db_session)
    terminal_activity_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db_session.add(
        Event(
            client_id=client.id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "echo recent", "shell": "bash", "sequence": 1},
            fingerprint=f"terminal_input_command:{window.id}:recent",
            created_at=terminal_activity_at,
        )
    )
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-1",
        "blob_id": "blob-user-1",
        "role": "user",
        "text": "please fix this bug",
    }
    event = managed_event_from_payload(client.id, window.id, "cursor_cli", payload)
    assert event is not None

    row = await persist_managed_agent_event(db_session, event)

    summary_job = (await db_session.execute(select(SummaryJob))).scalar_one()
    run_after = summary_job.run_after
    row_created_at = row.created_at
    if run_after.tzinfo is None:
        run_after = run_after.replace(tzinfo=timezone.utc)
    if row_created_at.tzinfo is None:
        row_created_at = row_created_at.replace(tzinfo=timezone.utc)
    assert summary_job.virtual_window_id == window.id
    assert summary_job.trigger_reason == "agent_idle"
    assert run_after == row_created_at + timedelta(seconds=20)

@pytest.mark.asyncio
async def test_index_managed_agent_event_if_ready_indexes_after_commit(db_session):
    client, window = await create_client_and_window(db_session)
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-1",
        "blob_id": "blob-1",
        "role": "assistant",
        "text": "managed cursor hello",
        "WEB_TERMINAL_PROJECT_PATH": "/workspace/project",
    }
    event = managed_event_from_payload(
        client.id,
        window.id,
        "cursor_cli",
        payload,
        source_path="/home/user/.cursor/store.db",
        cursor="root-1",
    )
    assert event is not None
    row = await persist_managed_agent_event(db_session, event)
    await db_session.commit()
    es_client = FakeElasticsearch()

    did_index = await agent_event_ingest.index_managed_agent_event_if_ready(db_session, es_client, row)
    await db_session.commit()

    assert did_index is True
    assert row.indexed_at is not None
    assert es_client.indexed_documents[0]["document"]["provider"] == "cursor_cli"
    assert es_client.indexed_documents[0]["document"]["session_id"] == "cursor-agent-1"
    assert es_client.indexed_documents[0]["document"]["text"] == "managed cursor hello"
    assert es_client.indexed_documents[0]["id"] == str(row.id)

@pytest.mark.asyncio
async def test_process_managed_agent_event_persists_indexes_and_invalidates(db_session):
    client, window = await create_client_and_window(db_session)
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-worker-1",
        "blob_id": "blob-worker-1",
        "role": "assistant",
        "text": "queued worker hello",
    }
    event = managed_event_from_payload(client.id, window.id, "cursor_cli", payload)
    assert event is not None
    es_client = FakeElasticsearch()
    ui_event_hub = CaptureUiEventHub()

    result = await process_managed_agent_event(
        db_session,
        event,
        es_client=es_client,
        ui_event_hub=ui_event_hub,
    )

    assert result.row.source_id == "cursor-agent-worker-1"
    assert result.row.indexed_at is not None
    assert result.resources == ("agent_record", "window", "search", "project_todos")
    assert es_client.indexed_documents[0]["document"]["text"]
    assert ui_event_hub.invalidations == [
        {
            "resources": ["agent_record", "window", "search", "project_todos"],
            "client_id": client.id,
            "window_id": window.id,
            "reason": "ai_event",
        }
    ]
    assert es_client.indexed_documents[0]["document"]["provider"] == "cursor_cli"
    assert es_client.indexed_documents[0]["document"]["session_id"] == "cursor-agent-worker-1"
    assert es_client.indexed_documents[0]["document"]["text"] == "queued worker hello"
    assert es_client.indexed_documents[0]["id"] == str(result.row.id)

@pytest.mark.asyncio
async def test_index_managed_agent_event_if_ready_skips_missing_client_or_already_indexed(db_session):
    client, window = await create_client_and_window(db_session)
    payload = {
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "agentId": "cursor-agent-1",
        "role": "assistant",
        "text": "managed cursor hello",
    }
    event = managed_event_from_payload(client.id, window.id, "cursor_cli", payload)
    assert event is not None
    row = await persist_managed_agent_event(db_session, event)
    await db_session.commit()
    es_client = FakeElasticsearch()

    assert await agent_event_ingest.index_managed_agent_event_if_ready(db_session, None, row) is False
    assert await agent_event_ingest.index_managed_agent_event_if_ready(db_session, es_client, row) is True
    assert await agent_event_ingest.index_managed_agent_event_if_ready(db_session, es_client, row) is False

    assert len(es_client.indexed_documents) == 1

@pytest.mark.asyncio
async def test_persist_managed_agent_event_rejects_mismatched_payload_window(db_session):
    client, window = await create_client_and_window(db_session)
    event = managed_event_from_payload(
        client.id,
        window.id,
        "cursor_cli",
        {
            "client_id": str(client.id),
            "virtual_window_id": str(window.id),
            "agentId": "cursor-agent-1",
            "role": "assistant",
            "text": "managed cursor hello",
        },
    )
    assert event is not None
    event.payload["virtual_window_id"] = str(uuid4())

    with pytest.raises(ValueError, match="event attribution does not match client/window"):
        await persist_managed_agent_event(db_session, event)

    assert (await db_session.execute(select(Event))).scalars().all() == []

@pytest.mark.asyncio
async def test_persist_managed_agent_event_uses_payload_project_path_when_event_project_missing(db_session):
    client, window = await create_client_and_window(db_session, cwd="/workspace/window-fallback")
    event = managed_event_from_payload(
        client.id,
        window.id,
        "cursor_cli",
        {
            "client_id": str(client.id),
            "virtual_window_id": str(window.id),
            "agentId": "cursor-agent-1",
            "role": "assistant",
            "text": "managed cursor hello",
            "WEB_TERMINAL_PROJECT_PATH": "/workspace/payload-project",
        },
        project_path="/workspace/explicit-project",
    )
    assert event is not None
    event = event.__class__(
        provider=event.provider,
        client_id=event.client_id,
        window_id=event.window_id,
        source_path=event.source_path,
        offset=event.offset,
        cursor=event.cursor,
        project_path=None,
        payload=event.payload,
    )

    row = await persist_managed_agent_event(db_session, event)

    ai_session = await db_session.get(AiSession, row.ai_session_id)
    assert ai_session is not None
    assert ai_session.project_path == "/workspace/payload-project"

@pytest.mark.asyncio
async def test_receive_managed_codex_trace_stores_payload_source_and_project_metadata(db_session):
    client, window = await create_client_and_window(db_session, cwd="/workspace/window-fallback")
    payload = {
        "trace_id": "trace-managed-1",
        "span": {"name": "tool_call", "attributes": {"tool": "bash"}},
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "source_path": "/home/user/.codex/trace.jsonl",
        "project_path": "/workspace/codex-project",
        "cursor": "cursor-42",
    }

    row = await receive_managed_codex_trace(
        db_session,
        payload,
        client_id=client.id,
        window_id=window.id,
    )

    ai_session = await db_session.get(AiSession, row.ai_session_id)
    assert ai_session is not None
    assert ai_session.provider == "codex"
    assert ai_session.source_id == "trace-managed-1"
    assert ai_session.source_path == "/home/user/.codex/trace.jsonl"
    assert ai_session.project_path == "/workspace/codex-project"


@pytest.mark.asyncio
async def test_receive_managed_codex_trace_keeps_rollout_session_stable_across_items(db_session):
    client, window = await create_client_and_window(db_session, cwd="/workspace/window-fallback")
    source_path = (
        "/home/user/.web-terminal-acp/codex-homes/"
        f"{window.id}/sessions/2026/06/23/"
        "rollout-2026-06-23T09-23-56-codex-session.jsonl"
    )
    first_payload = {
        "trace_id": "trace-item-1",
        "id": "trace-item-1:0",
        "payload": {"id": "trace-item-1"},
        "span": {"name": "response_item", "attributes": {"tool": "bash"}},
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "source_path": source_path,
    }
    second_payload = {
        "trace_id": "trace-item-2",
        "id": "trace-item-2:1",
        "payload": {"id": "trace-item-2"},
        "span": {"name": "response_item", "attributes": {"tool": "bash"}},
        "client_id": str(client.id),
        "virtual_window_id": str(window.id),
        "source_path": source_path,
    }

    first_row = await receive_managed_codex_trace(
        db_session,
        first_payload,
        client_id=client.id,
        window_id=window.id,
    )
    second_row = await receive_managed_codex_trace(
        db_session,
        second_payload,
        client_id=client.id,
        window_id=window.id,
    )
    await db_session.commit()

    ai_sessions = (await db_session.execute(select(AiSession))).scalars().all()
    assert first_row.id != second_row.id
    assert first_row.ai_session_id == second_row.ai_session_id
    assert len(ai_sessions) == 1
    assert ai_sessions[0].source_id == "codex-session"
