from tests.integration.test_summary_worker_support import *

@pytest.mark.asyncio
async def test_process_summary_job_returns_false_without_pending_job(session_factory):
    async with session_factory() as session:
        processed = await process_next_summary_job(session, FakeSummarizer())
        await session.commit()

    assert processed is False

@pytest.mark.asyncio
async def test_process_summary_jobs_once_opens_session_and_commits_processed_job(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    processed = await process_summary_jobs_once(
        session_factory,
        summarizer=FakeSummarizer(),
        es_client=FakeElasticsearch(),
    )

    assert processed is True
    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.succeeded

@pytest.mark.asyncio
async def test_process_summary_jobs_once_commits_claim_before_summarizing(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    observed_statuses: list[SummaryJobStatus] = []
    processed = await process_summary_jobs_once(
        session_factory,
        summarizer=ClaimObservingSummarizer(session_factory, observed_statuses),
        es_client=FakeElasticsearch(),
    )

    assert processed is True
    assert observed_statuses == [SummaryJobStatus.running]

@pytest.mark.asyncio
async def test_folder_creation_race_does_not_rollback_claimed_summary_job(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    inserted_conflict = False

    def insert_conflicting_folder(mapper, connection, target):
        nonlocal inserted_conflict
        if target.path != "/race" or inserted_conflict:
            return
        inserted_conflict = True
        connection.execute(
            Folder.__table__.insert().values(
                id=uuid4(),
                client_id=target.client_id,
                parent_id=target.parent_id,
                name=target.name,
                path=target.path,
            )
        )

    event.listen(Folder, "before_insert", insert_conflicting_folder)
    try:
        async with session_factory() as session:
            job = await claim_next_summary_job(session)
            assert job is not None

            window = await session.get(VirtualWindow, job.virtual_window_id)
            assert window is not None
            folder = await get_or_create_folder_by_path(session, window.client_id, "/race")
            await session.refresh(job)

            assert folder.path == "/race"
            assert job.status == SummaryJobStatus.running
            assert job.attempts == 1
    finally:
        event.remove(Folder, "before_insert", insert_conflicting_folder)

@pytest.mark.asyncio
async def test_process_summary_job_marks_missing_window_failed(session_factory):
    missing_window_id = uuid4()

    async with session_factory() as session:
        session.add(SummaryJob(virtual_window_id=missing_window_id, status=SummaryJobStatus.pending))
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FakeSummarizer())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.failed
        assert job.attempts == 1
        assert job.run_after is not None
        assert "window not found" in job.last_error

@pytest.mark.asyncio
async def test_process_summary_job_marks_summarizer_failure_retryable_with_bounded_error(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FailingSummarizer())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert job.attempts == 1
        assert job.run_after is not None
        assert job.last_error.startswith("LLM failed")
        assert len(job.last_error) <= 2000
        assert window.summary is None

@pytest.mark.asyncio
async def test_process_summary_job_marks_summarizer_failure_failed_after_max_attempts(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        job = await enqueue_summary_job(session, window.id)
        job.attempts = MAX_SUMMARY_JOB_ATTEMPTS - 1
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FailingSummarizer())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.failed
        assert job.attempts == MAX_SUMMARY_JOB_ATTEMPTS
        assert job.run_after is not None
        assert job.last_error.startswith("LLM failed")
        assert len(job.last_error) <= 2000

@pytest.mark.asyncio
async def test_collect_summary_context_uses_input_commands_in_chronological_order(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await session.flush()
        created_at_base = datetime(2026, 5, 20, tzinfo=timezone.utc)
        for index in range(60):
            session.add(
                Event(
                    source_type=EventSourceType.terminal,
                    source_id=f"terminal-{index}",
                    kind="terminal_input_command",
                    virtual_window_id=window.id,
                    payload_json={
                        "sequence": index,
                        "command": f"command-{index}",
                        "shell": "/bin/bash",
                        "captured_at": (created_at_base + timedelta(seconds=index)).isoformat(),
                    },
                    fingerprint=f"terminal-{index}",
                    created_at=created_at_base + timedelta(seconds=index),
                )
            )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert len(context) == 1
    assert [command["sequence"] for command in context[0]["payload"]["commands"]] == list(range(60))
    assert context[0]["source_type"] == "terminal"
    assert context[0]["kind"] == "terminal_input_context"

@pytest.mark.asyncio
async def test_collect_summary_context_does_not_use_large_terminal_output_as_primary_context(
    session_factory,
):
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add(
            Event(
                source_type=EventSourceType.terminal,
                source_id="terminal-large",
                kind="terminal_output",
                virtual_window_id=window.id,
                payload_json={"text": "x" * 20000},
                fingerprint="terminal-large",
            )
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["kind"] == "terminal_input_context"
    assert context[0]["payload"]["commands"] == []
    assert "x" * 20000 not in json.dumps(context)

@pytest.mark.asyncio
async def test_collect_summary_context_caps_total_serialized_budget(session_factory):
    max_total_bytes = 32768
    async with session_factory() as session:
        window = await create_local_window(session)
        created_at_base = datetime(2026, 5, 20, tzinfo=timezone.utc)
        for index in range(50):
            session.add(
                Event(
                    source_type=EventSourceType.terminal,
                    source_id=f"terminal-budget-{index}",
                    kind="terminal_input_command",
                    virtual_window_id=window.id,
                    payload_json={
                        "sequence": index,
                        "command": f"command-{index} " + ("x" * 1000),
                        "shell": "/bin/bash",
                        "captured_at": (created_at_base + timedelta(seconds=index)).isoformat(),
                    },
                    fingerprint=f"terminal-budget-{index}",
                    created_at=created_at_base + timedelta(seconds=index),
                )
            )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    serialized_size = len(
        json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    sequences = [command["sequence"] for command in context[0]["payload"]["commands"]]
    assert serialized_size <= max_total_bytes
    assert len(sequences) < 50
    assert sequences == list(range(50 - len(sequences), 50))
    assert context[0]["payload"]["truncation"] == {
        "total_commands": 50,
        "included_commands": len(sequences),
        "truncated": True,
        "budget_bytes": max_total_bytes,
    }

@pytest.mark.asyncio
async def test_process_summary_job_indexes_summary_by_default_and_closes_client(session_factory, monkeypatch):
    es_client = FakeElasticsearch()
    created_clients = []

    def fake_get_es_client():
        created_clients.append(es_client)
        return es_client

    monkeypatch.setattr(summary_worker, "get_es_client", fake_get_es_client, raising=False)

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()
        client_id = str(window.client_id)
        window_id = str(window.id)

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FakeSummarizer())
        await session.commit()

    assert processed is True
    assert created_clients == [es_client]
    assert es_client.closed is True
    assert es_client.indexed_documents == [
        {
            "index": SUMMARIES_INDEX,
            "id": window_id,
            "document": {
                "client_id": client_id,
                "virtual_window_id": window_id,
                "title": "[Claude] 修复 Nginx 403",
                "tags": ["nginx", "403"],
                "folder_path": "/2026-05/生产排障",
                "summary": "Fixed an nginx permission issue.",
                "text": "[Claude] 修复 Nginx 403 nginx 403 /2026-05/生产排障 Fixed an nginx permission issue.",
            },
        }
    ]

@pytest.mark.asyncio
async def test_process_summary_job_marks_retryable_when_es_client_construction_fails(
    session_factory, monkeypatch
):
    def fail_get_es_client():
        raise RuntimeError("Elasticsearch client unavailable " + ("x" * 3000))

    monkeypatch.setattr(summary_worker, "get_es_client", fail_get_es_client, raising=False)

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FakeSummarizer())
        await session.commit()
        assert processed is True

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert job.attempts == 1
        assert job.run_after is not None
        assert "summary indexing failed" in job.last_error
        assert "Elasticsearch client unavailable" in job.last_error
        assert len(job.last_error) <= 2000

@pytest.mark.asyncio
async def test_process_summary_job_propagates_sqlalchemy_errors_without_marking_failed(
    session_factory, monkeypatch
):
    async def fail_collect_summary_context(session, window):
        raise SQLAlchemyError("transaction is aborted")

    monkeypatch.setattr(
        summary_worker, "collect_summary_context", fail_collect_summary_context, raising=False
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(SQLAlchemyError, match="transaction is aborted"):
            await process_next_summary_job(session, FakeSummarizer())
        await session.rollback()

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert job.last_error is None

@pytest.mark.asyncio
async def test_process_summary_jobs_once_releases_claimed_job_after_sqlalchemy_error(
    session_factory,
    monkeypatch,
):
    async def fail_collect_summary_context(session, window):
        raise SQLAlchemyError("transaction is aborted")

    monkeypatch.setattr(
        summary_worker, "collect_summary_context", fail_collect_summary_context, raising=False
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()

    with pytest.raises(SQLAlchemyError, match="transaction is aborted"):
        await process_summary_jobs_once(
            session_factory,
            summarizer=FakeSummarizer(),
            es_client=FakeElasticsearch(),
        )

    async with session_factory() as session:
        job = (await session.execute(select(SummaryJob))).scalar_one()
        assert job.status == SummaryJobStatus.pending
        assert job.attempts == 1
        assert job.run_after is not None
        assert job.last_error == "summary processing transaction failed"

@pytest.mark.asyncio
async def test_process_summary_job_indexes_summary_with_deterministic_id(session_factory):
    es_client = FakeElasticsearch()

    async with session_factory() as session:
        window = await create_local_window(session)
        await enqueue_summary_job(session, window.id)
        await session.commit()
        client_id = str(window.client_id)
        window_id = str(window.id)

    async with session_factory() as session:
        processed = await process_next_summary_job(session, FakeSummarizer(), es_client=es_client)
        await session.commit()

    assert processed is True
    assert es_client.indexed_documents == [
        {
            "index": SUMMARIES_INDEX,
            "id": window_id,
            "document": {
                "client_id": client_id,
                "virtual_window_id": window_id,
                "title": "[Claude] 修复 Nginx 403",
                "tags": ["nginx", "403"],
                "folder_path": "/2026-05/生产排障",
                "summary": "Fixed an nginx permission issue.",
                "text": "[Claude] 修复 Nginx 403 nginx 403 /2026-05/生产排障 Fixed an nginx permission issue.",
            },
        }
    ]
