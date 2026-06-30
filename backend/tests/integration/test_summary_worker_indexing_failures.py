from tests.integration.test_summary_worker_support import *

@pytest.mark.asyncio
async def test_process_summary_job_marks_retryable_when_summary_indexing_fails(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(
            session, FakeSummarizer(), es_client=FakeElasticsearch(fail=True)
        )
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert job.run_after is not None
        assert "summary indexing failed" in job.last_error
        assert "Elasticsearch unavailable" in job.last_error
        assert window.summary == "Fixed an nginx permission issue."

@pytest.mark.asyncio
async def test_process_summary_job_succeeds_when_summary_index_blocked_by_flood_stage(
    session_factory,
):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(
            session,
            FakeSummarizer(),
            es_client=FloodStageBlockedElasticsearch(),
        )
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        assert job.status == SummaryJobStatus.succeeded
        assert job.run_after is None
        assert job.attempts == 1
        assert "summary search indexing skipped" in job.last_error
        assert "flood-stage watermark" in job.last_error
        assert window.summary == "Fixed an nginx permission issue."
