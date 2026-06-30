import json

from dataclasses import dataclass

from datetime import datetime, timedelta, timezone

from uuid import UUID, uuid4

import pytest

from sqlalchemy import event, select

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sqlalchemy.orm import selectinload

from app.model_base import Base

from app.models import (
    Event,
    EventSourceType,
    Folder,
    FolderSplitJob,
    FolderSplitJobStatus,
    SummaryJob,
    SummaryJobStatus,
    VirtualWindow,
    WindowTitleHistory,
)

from app.repositories.clients import ensure_local_client

from app.repositories.folders import get_or_create_folder_by_path

from app.repositories.summary_jobs import (
    MAX_SUMMARY_JOB_ATTEMPTS,
    claim_next_summary_job,
    collect_summary_context,
    enqueue_summary_job,
    get_latest_summary_job,
)

from app.contexts.windows.infrastructure.repository import create_window

from app.services import summary_worker

from app.services.search_index import SUMMARIES_INDEX

from app.services.summarizer import SummaryResult

from app.services.summary_worker import process_next_summary_job, process_summary_jobs_once

@dataclass
class FakeSummarizer:
    seen_context: list[dict] | None = None

    async def summarize(self, context_items):
        self.seen_context = context_items
        return SummaryResult(
            title="[Claude] 修复 Nginx 403",
            summary="Fixed an nginx permission issue.",
            tags=["nginx", "403"],
            folder_path="/2026-05/生产排障",
        )

class FailingSummarizer:
    async def summarize(self, context_items):
        raise RuntimeError("LLM failed " + ("x" * 3000))

@dataclass
class FollowupThenFailingSummarizer:
    session_factory: async_sessionmaker
    window_id: UUID
    followup_job_id: object | None = None

    async def summarize(self, context_items):
        async with self.session_factory() as session:
            job = await enqueue_summary_job(
                session,
                self.window_id,
                trigger_reason="agent_idle",
                run_after=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            await session.commit()
            self.followup_job_id = job.id
        raise RuntimeError("LLM failed while follow-up is pending")

@dataclass
class ResultSummarizer:
    result: SummaryResult
    seen_context: list[dict] | None = None

    async def summarize(self, context_items):
        self.seen_context = context_items
        return self.result

class FakeElasticsearch:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.indexed_documents = []
        self.closed = False

    async def index(self, **kwargs):
        if self.fail:
            raise RuntimeError("Elasticsearch unavailable")
        self.indexed_documents.append(kwargs)
        return {"result": "created"}

    async def close(self):
        self.closed = True

class FloodStageBlockedElasticsearch:
    async def index(self, **kwargs):
        raise RuntimeError(
            "ApiError(429, 'cluster_block_exception', "
            "'index [summaries] blocked by: "
            "[TOO_MANY_REQUESTS/12/disk usage exceeded flood-stage watermark, "
            "index has read-only-allow-delete block];')"
        )

@dataclass
class ClaimObservingSummarizer:
    session_factory: async_sessionmaker
    observed_statuses: list[SummaryJobStatus]

    async def summarize(self, context_items):
        async with self.session_factory() as session:
            job = (await session.execute(select(SummaryJob))).scalar_one()
            self.observed_statuses.append(job.status)
        return SummaryResult(
            title="Observed claim",
            summary="Summary job claim was committed before summarization.",
            tags=["summary"],
            folder_path="/observed",
        )

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

async def create_local_window(session):
    client = await ensure_local_client(session)
    return await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")

async def create_window_in_folder(session, client_id, folder_id):
    window = await create_window(session, client_id, cwd="/tmp", shell_command="/bin/bash")
    window.folder_id = folder_id
    await session.flush()
    return window

__all__ = [name for name in globals() if not name.startswith("__")]
