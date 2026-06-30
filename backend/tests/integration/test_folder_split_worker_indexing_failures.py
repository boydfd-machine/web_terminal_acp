from tests.integration.test_folder_split_worker_support import *

@pytest.mark.asyncio
async def test_summary_index_failure_after_moves_marks_job_retryable(session_factory):
    splitter = FakeFolderSplitter()
    es_client = FakeElasticsearch(fail=True)

    async with session_factory() as session:
        windows = await create_windows_in_folder(session, "/开发调试", 6)
        parent_folder = await get_or_create_folder_by_path(session, windows[0].client_id, "/开发调试")
        await enqueue_folder_split_job(session, windows[0].client_id, parent_folder.id)
        await session.commit()
        expected_indexed_ids = {str(window.id) for window in windows}

    async with session_factory() as session:
        processed = await process_next_folder_split_job(session, splitter, es_client=es_client)
        await session.commit()

    assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(FolderSplitJob))).scalar_one()
        assert job.status == FolderSplitJobStatus.pending
        assert job.run_after is not None
        assert job.last_error == "summary indexing failed: Elasticsearch unavailable"
        job.run_after = None
        await session.commit()

    retry_es_client = FakeElasticsearch()
    async with session_factory() as session:
        processed = await process_next_folder_split_job(
            session,
            FailingFolderSplitter(),
            es_client=retry_es_client,
        )
        await session.commit()

    assert processed is True
    assert {document["id"] for document in retry_es_client.indexed_documents} == expected_indexed_ids

    async with session_factory() as session:
        job = (await session.execute(select(FolderSplitJob))).scalar_one()
        assert job.status == FolderSplitJobStatus.succeeded
        assert job.last_error is None
