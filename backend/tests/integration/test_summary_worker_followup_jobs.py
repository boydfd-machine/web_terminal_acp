from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import SummaryJob, SummaryJobStatus
from app.repositories.summary_jobs import claim_next_summary_job, enqueue_summary_job, get_latest_summary_job
from app.services.summary_worker import process_summary_jobs_once
from tests.integration.test_summary_worker_support import (
    FakeElasticsearch,
    FakeSummarizer,
    FollowupThenFailingSummarizer,
    create_local_window,
)

pytest_plugins = ("tests.integration.test_summary_worker_support",)


@pytest.mark.asyncio
async def test_process_summary_jobs_once_releases_failed_running_job_with_pending_followup(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        original_job = await enqueue_summary_job(session, window.id)
        await session.commit()

    summarizer = FollowupThenFailingSummarizer(session_factory, window.id)
    processed = await process_summary_jobs_once(
        session_factory,
        summarizer=summarizer,
        es_client=FakeElasticsearch(),
    )

    assert processed is True
    async with session_factory() as session:
        jobs = list(await session.scalars(select(SummaryJob).order_by(SummaryJob.created_at, SummaryJob.id)))
        original = next(job for job in jobs if job.id == original_job.id)
        followup = next(job for job in jobs if job.id == summarizer.followup_job_id)
        assert original.status == SummaryJobStatus.failed
        assert original.attempts == 1
        assert original.last_error.startswith("LLM failed while follow-up is pending")
        assert followup.status == SummaryJobStatus.pending

    processed = await process_summary_jobs_once(
        session_factory,
        summarizer=FakeSummarizer(),
        es_client=FakeElasticsearch(),
    )

    assert processed is True
    async with session_factory() as session:
        followup = await session.get(SummaryJob, summarizer.followup_job_id)
        assert followup is not None
        assert followup.status == SummaryJobStatus.succeeded


@pytest.mark.asyncio
async def test_claim_next_summary_job_releases_stale_running_job_with_due_followup(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        running = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.running,
            attempts=1,
            created_at=stale_at,
            updated_at=stale_at,
        )
        pending = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.pending,
            run_after=stale_at,
            created_at=stale_at + timedelta(seconds=1),
            updated_at=stale_at + timedelta(seconds=1),
        )
        session.add_all([running, pending])
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_summary_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.id == pending.id
    assert claimed.status == SummaryJobStatus.running
    async with session_factory() as session:
        running = await session.get(SummaryJob, running.id)
        assert running is not None
        assert running.status == SummaryJobStatus.failed
        assert running.last_error == "summary job superseded by pending follow-up"


@pytest.mark.asyncio
async def test_get_latest_summary_job_prefers_active_followup_over_recent_failed_job(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        now = datetime.now(timezone.utc)
        failed = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.failed,
            updated_at=now,
            created_at=now,
        )
        pending = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.pending,
            run_after=now - timedelta(seconds=1),
            updated_at=now - timedelta(seconds=10),
            created_at=now - timedelta(seconds=10),
        )
        session.add_all([failed, pending])
        await session.commit()

    async with session_factory() as session:
        latest = await get_latest_summary_job(session, window.id)

    assert latest is not None
    assert latest.id == pending.id
