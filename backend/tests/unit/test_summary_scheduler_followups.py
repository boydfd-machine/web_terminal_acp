from tests.unit.test_summary_scheduler_support import *
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

@pytest.mark.asyncio
async def test_agent_user_message_after_recent_terminal_activity_schedules_summary_after_idle(db_session):
    window = await create_window(db_session)
    shell_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    user_message_at = shell_at + timedelta(minutes=2)
    await add_shell_input(db_session, window, shell_at, 1)
    event = await add_agent_event(db_session, window, user_message_at, fingerprint="agent-user-1", kind="user_message")

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    assert job.run_after == user_message_at + timedelta(seconds=20)
    assert job.trigger_reason == AGENT_IDLE_REASON

@pytest.mark.asyncio
async def test_repeat_agent_events_in_same_burst_do_not_reschedule_after_summary(db_session):
    window = await create_window(db_session)
    first_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    second_at = first_at + timedelta(seconds=30)
    db_session.add(
        SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.succeeded,
            updated_at=first_at + timedelta(minutes=3),
            created_at=first_at + timedelta(minutes=3),
        )
    )
    await add_agent_event(db_session, window, first_at, fingerprint="agent-1", kind="user_message")
    first_event = await add_agent_event(db_session, window, first_at, fingerprint="agent-3", kind="user_message")
    await schedule_summary_after_agent_activity(db_session, window, event=first_event)
    event = await add_agent_event(
        db_session,
        window,
        second_at,
        fingerprint="agent-2",
        kind="user_message",
    )

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is None

@pytest.mark.asyncio
async def test_new_agent_burst_after_idle_schedules_again(db_session):
    window = await create_window(db_session)
    first_burst = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    second_burst = first_burst + timedelta(minutes=10)
    db_session.add(
        SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.succeeded,
            updated_at=first_burst + timedelta(minutes=3),
            created_at=first_burst + timedelta(minutes=3),
        )
    )
    first_event = await add_agent_event(
        db_session,
        window,
        first_burst,
        fingerprint="agent-1",
        kind="user_message",
    )
    await schedule_summary_after_agent_activity(db_session, window, event=first_event)
    event = await add_agent_event(
        db_session,
        window,
        second_burst,
        fingerprint="agent-2",
        kind="user_message",
    )

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    assert job.run_after == second_burst + timedelta(seconds=20)

@pytest.mark.asyncio
async def test_pending_followup_waits_until_running_job_completes(db_session):
    window = await create_window(db_session)
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    running = SummaryJob(virtual_window_id=window.id, status=SummaryJobStatus.running)
    pending = SummaryJob(
        virtual_window_id=window.id,
        status=SummaryJobStatus.pending,
        run_after=now - timedelta(seconds=1),
        trigger_reason="input_idle",
        input_generation=2,
    )
    db_session.add_all([running, pending])
    await db_session.flush()

    blocked_claim = await claim_next_summary_job(db_session)
    assert blocked_claim is None

    running.status = SummaryJobStatus.succeeded
    await db_session.flush()
    followup_claim = await claim_next_summary_job(db_session)

    assert followup_claim is not None
    assert followup_claim.id == pending.id
    assert followup_claim.status == SummaryJobStatus.running

@pytest.mark.asyncio
async def test_running_job_is_not_preempted_and_new_pending_job_can_follow(db_session):
    window = await create_window(db_session)
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    running = SummaryJob(
        virtual_window_id=window.id,
        status=SummaryJobStatus.running,
        run_after=None,
        trigger_reason="input_idle",
        input_generation=1,
    )
    db_session.add(running)
    await add_input_event(db_session, window, now, 2)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.id != running.id
    assert job.status == SummaryJobStatus.pending
    assert job.run_after == now + timedelta(seconds=20)
    assert running.status == SummaryJobStatus.running

@pytest.mark.asyncio
async def test_enqueue_summary_job_updates_existing_after_concurrent_insert():
    window_id = uuid4()
    existing = SummaryJob(
        virtual_window_id=window_id,
        status=SummaryJobStatus.pending,
        run_after=datetime(2026, 5, 21, 12, 30, tzinfo=timezone.utc),
        trigger_reason="old_reason",
        input_generation=1,
    )

    class FailedNestedTransaction:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def __init__(self):
            self.flush_calls = 0
            self.scalar_calls = 0
            self.added: list[SummaryJob] = []
            self.rolled_back = False

        async def scalar(self, _statement):
            self.scalar_calls += 1
            return None if self.scalar_calls == 1 else existing

        def begin_nested(self):
            return FailedNestedTransaction()

        def add(self, job: SummaryJob):
            self.added.append(job)

        async def flush(self):
            self.flush_calls += 1
            if self.flush_calls == 1:
                raise IntegrityError("INSERT INTO summary_jobs", {}, Exception("duplicate"))

        async def rollback(self):
            self.rolled_back = True

    session = FakeSession()

    run_after = datetime(2026, 5, 21, 12, 0, 20, tzinfo=timezone.utc)
    job = await enqueue_summary_job(
        session,  # type: ignore[arg-type]
        window_id,
        trigger_reason=AGENT_IDLE_REASON,
        input_generation=2,
        run_after=run_after,
        update_existing=True,
    )

    assert job is existing
    assert job.run_after == run_after
    assert job.trigger_reason == AGENT_IDLE_REASON
    assert job.input_generation == 2
    assert session.flush_calls == 2
    assert not session.rolled_back


def test_pending_summary_job_postgres_conflict_predicate_matches_partial_index():
    from app.contexts.workspace.infrastructure.summary_jobs_repository.job_repository import (
        _pending_summary_job_insert_statement,
    )

    statement = _pending_summary_job_insert_statement(
        postgresql_insert,
        uuid4(),
        uuid4(),
        trigger_reason=AGENT_IDLE_REASON,
        allow_title_folder_override=False,
        input_generation=1,
        run_after=datetime(2026, 5, 21, 12, 0, 20, tzinfo=timezone.utc),
    )
    compiled = statement.compile(dialect=postgresql_dialect())

    assert "ON CONFLICT (virtual_window_id) WHERE status = 'PENDING'" in str(compiled)
    assert "status_1" not in compiled.params
