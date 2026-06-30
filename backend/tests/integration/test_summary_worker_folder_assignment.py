import re

from tests.integration.test_summary_worker_support import *

DEFAULT_TERMINAL_TITLE_PATTERN = r"^Terminal \d{2}/\d{2} \d{2}:\d{2}$"

@pytest.mark.asyncio
async def test_process_summary_job_moves_window_to_llm_folder(session_factory):
    summarizer = FakeSummarizer()

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        window = (
            await session.execute(
                select(VirtualWindow).options(selectinload(VirtualWindow.folder))
            )
        ).scalar_one()
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert window.title == "[Claude] 修复 Nginx 403"
        assert window.summary == "Fixed an nginx permission issue."
        assert window.title_tags == ["nginx", "403"]
        assert job.status == SummaryJobStatus.succeeded
        assert job.attempts == 1
        assert window.folder.path == "/2026-05/生产排障"
        title_history = (
            await session.execute(
                select(WindowTitleHistory).order_by(WindowTitleHistory.created_at)
            )
        ).scalars().all()
        assert len(title_history) == 2
        assert re.match(DEFAULT_TERMINAL_TITLE_PATTERN, title_history[0].title)
        assert title_history[0].summary is None
        assert title_history[0].source == "initial"
        assert (title_history[1].title, title_history[1].summary, title_history[1].source) == (
            "[Claude] 修复 Nginx 403",
            "Fixed an nginx permission issue.",
            "summary",
        )

    assert summarizer.seen_context is not None
    assert len(summarizer.seen_context) == 1
    fallback_context = summarizer.seen_context[0]
    assert fallback_context["source_type"] == "terminal"
    assert fallback_context["kind"] == "terminal_input_context"
    assert re.match(DEFAULT_TERMINAL_TITLE_PATTERN, fallback_context["payload"]["window"]["title"])
    assert fallback_context["payload"]["window"]["cwd"] == "/tmp"
    assert fallback_context["payload"]["window"]["shell_command"] == "/bin/bash"
    assert fallback_context["payload"]["window"]["summary"] is None
    assert fallback_context["payload"]["window"]["title_tags"] is None
    assert fallback_context["payload"]["commands"] == []

@pytest.mark.asyncio
async def test_manual_title_lock_prevents_auto_title_overwrite_but_updates_summary_and_tags(
    session_factory,
):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto", "summary"],
            folder_path="/auto-folder",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        window.title = "Manual Title"
        window.title_manually_overridden = True
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        assert window.title == "Manual Title"
        assert window.summary == "Auto summary."
        assert window.title_tags == ["auto", "summary"]

@pytest.mark.asyncio
async def test_manual_folder_lock_prevents_auto_folder_overwrite_but_updates_summary_and_tags(
    session_factory,
):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto", "summary"],
            folder_path="/auto-folder",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        manual_folder = await get_or_create_folder_by_path(session, window.client_id, "/manual-folder")
        window.folder_id = manual_folder.id
        window.folder_manually_overridden = True
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        window = (
            await session.execute(select(VirtualWindow).options(selectinload(VirtualWindow.folder)))
        ).scalar_one()
        assert window.folder.path == "/manual-folder"
        assert window.summary == "Auto summary."
        assert window.title_tags == ["auto", "summary"]

@pytest.mark.asyncio
async def test_override_job_overwrites_manual_title_and_folder_and_clears_locks(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/auto-folder",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        manual_folder = await get_or_create_folder_by_path(session, window.client_id, "/manual-folder")
        window.title = "Manual Title"
        window.folder_id = manual_folder.id
        window.title_manually_overridden = True
        window.folder_manually_overridden = True
        job = await enqueue_summary_job(session, window.id)
        job.allow_title_folder_override = True
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        window = (
            await session.execute(select(VirtualWindow).options(selectinload(VirtualWindow.folder)))
        ).scalar_one()
        assert window.title == "Auto Title"
        assert window.folder.path == "/auto-folder"
        assert window.title_manually_overridden is False
        assert window.folder_manually_overridden is False

@pytest.mark.asyncio
async def test_invalid_folder_path_marks_summary_job_retryable_with_last_error(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="relative-folder",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert "folder path must be absolute" in job.last_error
        assert window.summary is None

@pytest.mark.asyncio
async def test_non_leaf_folder_path_moves_window_to_summary_fallback_leaf(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试",
        )
    )
    es_client = FakeElasticsearch()

    async with session_factory() as session:
        window = await create_local_window(session)
        await get_or_create_folder_by_path(session, window.client_id, "/开发调试")
        await get_or_create_folder_by_path(session, window.client_id, "/开发调试/后端摘要")
        await enqueue_summary_job(session, window.id)
        await session.commit()
        client_id = str(window.client_id)
        window_id = str(window.id)

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=es_client)
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (
            await session.execute(select(VirtualWindow).options(selectinload(VirtualWindow.folder)))
        ).scalar_one()
        assert job.status == SummaryJobStatus.succeeded
        assert job.last_error is None
        assert window.summary == "Auto summary."
        assert window.folder.path == "/开发调试/未分类"
    assert es_client.indexed_documents == [
        {
            "index": SUMMARIES_INDEX,
            "id": window_id,
            "document": {
                "client_id": client_id,
                "virtual_window_id": window_id,
                "title": "Auto Title",
                "tags": ["auto"],
                "folder_path": "/开发调试/未分类",
                "summary": "Auto summary.",
                "text": "Auto Title auto /开发调试/未分类 Auto summary.",
            },
        }
    ]

@pytest.mark.asyncio
async def test_manual_folder_lock_skips_invalid_llm_folder_but_updates_summary(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        manual_folder = await get_or_create_folder_by_path(session, window.client_id, "/manual-folder")
        window.folder_id = manual_folder.id
        window.folder_manually_overridden = True
        await get_or_create_folder_by_path(session, window.client_id, "/开发调试")
        await get_or_create_folder_by_path(session, window.client_id, "/开发调试/后端摘要")
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (
            await session.execute(select(VirtualWindow).options(selectinload(VirtualWindow.folder)))
        ).scalar_one()
        assert job.status == SummaryJobStatus.succeeded
        assert job.last_error is None
        assert window.folder.path == "/manual-folder"
        assert window.folder_manually_overridden is True
        assert window.summary == "Auto summary."
        assert window.title_tags == ["auto"]

@pytest.mark.asyncio
async def test_new_child_path_under_occupied_leaf_marks_summary_job_retryable_without_creating_child(
    session_factory,
):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试/后端摘要",
        )
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        occupied_leaf = await get_or_create_folder_by_path(session, window.client_id, "/开发调试")
        existing_window = await create_window_in_folder(session, window.client_id, occupied_leaf.id)
        await enqueue_summary_job(session, window.id)
        await session.commit()
        existing_window_id = existing_window.id

    async with session_factory() as session:
        processed = await process_next_summary_job(session, summarizer, es_client=FakeElasticsearch())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        folders = list(await session.scalars(select(Folder).order_by(Folder.path)))
        existing_window = await session.get(VirtualWindow, existing_window_id)
        assert existing_window is not None
        occupied_folder = next(folder for folder in folders if folder.path == "/开发调试")
        assert job.status == SummaryJobStatus.pending
        assert "folder_path would create a child under an occupied leaf topic" in job.last_error
        assert "/开发调试/后端摘要" not in {folder.path for folder in folders}
        assert existing_window.folder_id == occupied_folder.id

@pytest.mark.asyncio
async def test_process_summary_job_enqueues_split_when_leaf_exceeds_five_windows(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试",
        )
    )

    async with session_factory() as session:
        target_window = await create_local_window(session)
        target_folder = await get_or_create_folder_by_path(
            session, target_window.client_id, "/开发调试"
        )
        for _ in range(5):
            await create_window_in_folder(session, target_window.client_id, target_folder.id)
        await enqueue_summary_job(session, target_window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(
            session, summarizer, es_client=FakeElasticsearch()
        )
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        split_job = (await session.execute(select(FolderSplitJob))).scalar_one()
        assert split_job.status == FolderSplitJobStatus.pending
        assert split_job.folder_id == target_folder.id
        assert split_job.client_id == target_window.client_id

@pytest.mark.asyncio
async def test_process_summary_job_does_not_enqueue_split_at_exactly_five_windows(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试",
        )
    )

    async with session_factory() as session:
        target_window = await create_local_window(session)
        target_folder = await get_or_create_folder_by_path(
            session, target_window.client_id, "/开发调试"
        )
        for _ in range(4):
            await create_window_in_folder(session, target_window.client_id, target_folder.id)
        await enqueue_summary_job(session, target_window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(
            session, summarizer, es_client=FakeElasticsearch()
        )
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        split_jobs = list(await session.scalars(select(FolderSplitJob)))
        assert split_jobs == []

@pytest.mark.asyncio
async def test_manual_folder_lock_does_not_enqueue_split_for_llm_target(session_factory):
    summarizer = ResultSummarizer(
        SummaryResult(
            title="Auto Title",
            summary="Auto summary.",
            tags=["auto"],
            folder_path="/开发调试",
        )
    )

    async with session_factory() as session:
        target_window = await create_local_window(session)
        manual_folder = await get_or_create_folder_by_path(
            session, target_window.client_id, "/manual-folder"
        )
        target_window.folder_id = manual_folder.id
        target_window.folder_manually_overridden = True
        llm_folder = await get_or_create_folder_by_path(
            session, target_window.client_id, "/开发调试"
        )
        for _ in range(6):
            await create_window_in_folder(session, target_window.client_id, llm_folder.id)
        await enqueue_summary_job(session, target_window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(
            session, summarizer, es_client=FakeElasticsearch()
        )
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        split_jobs = list(await session.scalars(select(FolderSplitJob)))
        window = (
            await session.execute(
                select(VirtualWindow).where(VirtualWindow.id == target_window.id)
            )
        ).scalar_one()
        assert split_jobs == []
        assert window.folder_id == manual_folder.id
