from tests.unit.test_summary_scheduler_support import *

from app.contexts.workspace.application import summary_scheduler as summary_scheduler_service
from app.config import get_settings
from app.contexts.workspace.infrastructure.project_todos_repository import (
    complete_project_todos_after_artifact_status_change,
)
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus
from tests.unit.test_terminal_work_status_support import claude_completion_payload

@pytest.mark.asyncio
async def test_settings_include_terminal_summary_defaults(monkeypatch):
    settings = Settings(_env_file=None)

    assert settings.terminal_summary_idle_seconds == 20
    assert settings.terminal_summary_initial_max_wait_seconds == 120
    assert settings.terminal_summary_repeat_seconds == 600

@pytest.mark.asyncio
async def test_first_input_schedules_after_idle_window(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    await add_input_event(db_session, window, first_input_at, 1)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.status == SummaryJobStatus.pending
    assert job.run_after == first_input_at + timedelta(seconds=20)
    assert job.trigger_reason == "input_idle"
    assert job.input_generation == 1

@pytest.mark.asyncio
async def test_ephemeral_window_does_not_schedule_summary_jobs(db_session):
    window = await create_window(db_session)
    window.derived_mode = "ephemeral"
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    await add_input_event(db_session, window, now, 1)

    terminal_job = await schedule_summary_after_terminal_input(db_session, window)
    agent_event = await add_agent_event(
        db_session,
        window,
        now + timedelta(seconds=1),
        fingerprint="agent-ephemeral-1",
        kind="user_message",
    )
    agent_job = await schedule_summary_after_agent_activity(db_session, window, event=agent_event)

    assert terminal_job is None
    assert agent_job is None
    assert (await db_session.execute(select(SummaryJob))).scalars().all() == []

@pytest.mark.asyncio
async def test_sustained_input_reschedules_to_latest_input_plus_idle(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    last_input_at = first_input_at + timedelta(seconds=10)
    await add_input_event(db_session, window, first_input_at, 1)
    await add_input_event(db_session, window, last_input_at, 2)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.run_after == last_input_at + timedelta(seconds=20)
    assert job.trigger_reason == "input_idle"
    assert job.input_generation == 2

@pytest.mark.asyncio
async def test_sustained_input_uses_initial_max_wait(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    last_input_at = first_input_at + timedelta(seconds=110)
    await add_input_event(db_session, window, first_input_at, 1)
    await add_input_event(db_session, window, last_input_at, 2)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.run_after == first_input_at + timedelta(minutes=2)
    assert job.trigger_reason == "input_initial_max_wait"
    assert job.input_generation == 2

@pytest.mark.asyncio
async def test_repeat_after_succeeded_summary_uses_ten_minute_limit(db_session):
    window = await create_window(db_session)
    last_summary_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    last_input_at = last_summary_at + timedelta(minutes=20)
    db_session.add(
        SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.succeeded,
            updated_at=last_summary_at,
            created_at=last_summary_at,
        )
    )
    await add_input_event(db_session, window, last_input_at, 1)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.run_after == last_summary_at + timedelta(seconds=600)
    assert job.trigger_reason == "input_repeat"

@pytest.mark.asyncio
async def test_plain_terminal_input_schedules_summary_job(db_session):
    window = await create_window(db_session)
    captured_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    await db_session.commit()

    await record_terminal_input_command(
        db_session,
        client_id=window.client_id,
        window_id=window.id,
        raw_command="echo hello",
        shell="bash",
        cwd="/workspace/project",
        captured_at=captured_at,
        sequence=1,
    )

    jobs = (await db_session.execute(select(SummaryJob))).scalars().all()
    assert len(jobs) == 1
    run_after = jobs[0].run_after
    if run_after.tzinfo is None:
        run_after = run_after.replace(tzinfo=timezone.utc)
    assert run_after == captured_at + timedelta(seconds=20)
    assert jobs[0].trigger_reason == "input_idle"

@pytest.mark.asyncio
async def test_agent_tool_record_activity_does_not_extend_input_idle_window(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    agent_activity_at = first_input_at + timedelta(seconds=5)
    await add_input_event(db_session, window, first_input_at, 1)
    await add_agent_event(db_session, window, agent_activity_at, fingerprint="cursor-agent-activity")

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.run_after == first_input_at + timedelta(seconds=20)
    assert job.trigger_reason == "input_idle"

@pytest.mark.asyncio
async def test_terminal_output_does_not_extend_input_idle_window(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    output_at = first_input_at + timedelta(seconds=5)
    await add_input_event(db_session, window, first_input_at, 1)
    db_session.add(
        Event(
            client_id=window.client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_output",
            virtual_window_id=window.id,
            payload_json={"text": "command output\n"},
            fingerprint=f"terminal_output:{window.id}:1",
            created_at=output_at,
        )
    )
    await db_session.flush()

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job is not None
    assert job.run_after == first_input_at + timedelta(seconds=20)

@pytest.mark.asyncio
async def test_existing_pending_job_updates_run_after_reason_and_generation(db_session):
    window = await create_window(db_session)
    first_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    pending = SummaryJob(
        virtual_window_id=window.id,
        status=SummaryJobStatus.pending,
        run_after=first_input_at + timedelta(minutes=5),
        trigger_reason="old_reason",
        input_generation=0,
    )
    db_session.add(pending)
    await add_input_event(db_session, window, first_input_at, 1)

    job = await schedule_summary_after_terminal_input(db_session, window)

    assert job.id == pending.id
    assert job.run_after == first_input_at + timedelta(seconds=20)
    assert job.trigger_reason == "input_idle"
    assert job.input_generation == 1

@pytest.mark.asyncio
async def test_first_agent_activity_after_idle_schedules_summary(db_session):
    window = await create_window(db_session)
    agent_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = await add_agent_event(db_session, window, agent_at, fingerprint="agent-1", kind="user_message")

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    assert job.status == SummaryJobStatus.pending
    assert job.run_after == agent_at + timedelta(seconds=20)
    assert job.trigger_reason == AGENT_IDLE_REASON
    assert job.input_generation == 1

@pytest.mark.asyncio
async def test_project_todo_dispatch_schedules_summary_after_idle(db_session):
    window = await create_window(db_session)
    dispatched_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)

    job = await schedule_summary_after_project_todo_dispatch(
        db_session,
        window,
        dispatched_at=dispatched_at,
    )

    assert job is not None
    assert job.status == SummaryJobStatus.pending
    assert job.run_after == dispatched_at + timedelta(seconds=20)
    assert job.trigger_reason == PROJECT_TODO_DISPATCH_REASON
    assert job.input_generation == 1
    assert window.agent_activity_latest_at == dispatched_at
    assert window.agent_activity_latest_user_input_at == dispatched_at

@pytest.mark.asyncio
async def test_first_agent_activity_ignores_current_event_in_prior_idle_check(db_session):
    window = await create_window(db_session)
    agent_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = await add_agent_event(db_session, window, agent_at, fingerprint="agent-current", kind="user_message")

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    assert job.run_after == agent_at + timedelta(seconds=20)

@pytest.mark.asyncio
async def test_agent_activity_without_prior_idle_does_not_schedule(db_session):
    window = await create_window(db_session)
    shell_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    agent_at = shell_at + timedelta(minutes=2)
    await add_shell_input(db_session, window, shell_at, 1)
    event = await add_agent_event(db_session, window, agent_at, fingerprint="agent-1")

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is None

@pytest.mark.asyncio
async def test_agent_activity_scheduler_avoids_terminal_output_scans(counted_db_session):
    db_session, statements = counted_db_session
    window = await create_window(db_session)
    agent_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = await add_agent_event(
        db_session,
        window,
        agent_at,
        fingerprint="agent-no-output-scan",
    )
    statements.clear()

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    event_reads = [
        statement
        for statement in statements
        if "FROM events" in statement and "SELECT events" in statement
    ]
    assert event_reads
    assert all(" OR " not in statement.upper() for statement in event_reads)
    assert all("terminal_output" not in statement for statement in event_reads)
    source_time_reads = [
        statement
        for statement in statements
        if "FROM events" in statement
        and "events.created_at" in statement
        and "events.source_type IN" in statement
    ]
    assert len(source_time_reads) == 1
    assert "LIMIT" in source_time_reads[0].upper()

@pytest.mark.asyncio
async def test_duplicate_agent_activity_does_not_advance_generation(db_session):
    window = await create_window(db_session)
    agent_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = await add_agent_event(db_session, window, agent_at, fingerprint="agent-repeat", kind="user_message")

    first_job = await schedule_summary_after_agent_activity(db_session, window, event=event)
    second_job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert first_job is not None
    assert second_job is not None
    assert window.agent_activity_generation == 1
    assert second_job.input_generation == 1

@pytest.mark.asyncio
async def test_agent_completion_updates_window_activity_completion_state(db_session):
    window = await create_window(db_session)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="event_msg",
        virtual_window_id=window.id,
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {"type": "task_completed"},
            "timestamp": completed_at.isoformat(),
        },
        fingerprint="agent-completion-window-state",
        created_at=completed_at + timedelta(milliseconds=30),
    )
    db_session.add(event)
    await db_session.flush()

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert window.agent_activity_latest_at == completed_at
    assert window.agent_activity_latest_completed_at == completed_at

@pytest.mark.asyncio
async def test_agent_completion_marks_assigned_project_todo_awaiting_review(db_session):
    window = await create_window(db_session)
    dispatched_at = datetime(2026, 5, 21, 11, 59, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        client_id=window.client_id,
        project_path="/workspace/project",
        title="Fix flaky test",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatched_at=dispatched_at,
    )
    db_session.add(todo)
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="event_msg",
        virtual_window_id=window.id,
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {"type": "task_completed"},
            "timestamp": completed_at.isoformat(),
        },
        fingerprint="agent-completion-project-todo",
        created_at=completed_at + timedelta(milliseconds=30),
    )
    db_session.add(event)
    await db_session.flush()

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert todo.status == ProjectTodoStatus.awaiting_review
    assert todo.awaiting_review_at == completed_at
    assert todo.review_unseen is True


@pytest.mark.asyncio
async def test_agent_completion_passes_registry_to_verification_scheduler(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    registry = object()
    captured = []

    def fake_make_verification_scheduler(**kwargs):
        captured.append(kwargs)

        def scheduler(_todo, _completed_at):
            return True

        return scheduler

    monkeypatch.setattr(summary_scheduler_service, "make_verification_scheduler", fake_make_verification_scheduler)
    window = await create_window(db_session)
    dispatched_at = datetime(2026, 5, 21, 11, 59, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        client_id=window.client_id,
        project_path="/workspace/project",
        title="Fix remote background task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatched_at=dispatched_at,
    )
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="assistant_message",
        virtual_window_id=window.id,
        payload_json=claude_completion_payload(),
        fingerprint="agent-completion-registry",
        created_at=completed_at,
    )
    db_session.add_all([todo, event])
    await db_session.flush()

    await schedule_summary_after_agent_activity(db_session, window, event=event, registry=registry)

    assert captured == [{"client_id": window.client_id, "window_id": window.id, "registry": registry}]
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"


@pytest.mark.asyncio
async def test_duplicate_agent_completion_does_not_reschedule_verification(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    scheduled = []

    def fake_make_verification_scheduler(**kwargs):
        def scheduler(_todo, _completed_at):
            scheduled.append(kwargs)
            return True

        return scheduler

    monkeypatch.setattr(summary_scheduler_service, "make_verification_scheduler", fake_make_verification_scheduler)
    window = await create_window(db_session)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        client_id=window.client_id,
        project_path="/workspace/project",
        title="Do work once",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatched_at=completed_at - timedelta(minutes=1),
    )
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="assistant_message",
        virtual_window_id=window.id,
        payload_json=claude_completion_payload(),
        fingerprint="duplicate-agent-completion",
        created_at=completed_at,
    )
    db_session.add_all([todo, event])
    await db_session.flush()

    await schedule_summary_after_agent_activity(db_session, window, event=event)
    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert len(scheduled) == 1
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"

@pytest.mark.asyncio
async def test_agent_completion_schedules_requested_artifacts_before_review(db_session, monkeypatch):
    window = await create_window(db_session)
    dispatched_at = datetime(2026, 5, 21, 11, 59, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        client_id=window.client_id,
        project_path="/workspace/project",
        title="Fix flaky artifact",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatched_at=dispatched_at,
        artifact_kinds_json=["agent_trace_graph"],
    )
    db_session.add(todo)
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-artifact",
        kind="event_msg",
        virtual_window_id=window.id,
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {"type": "task_completed"},
            "timestamp": completed_at.isoformat(),
        },
        fingerprint="agent-completion-project-todo-artifact",
        created_at=completed_at + timedelta(milliseconds=30),
    )
    db_session.add(event)
    await db_session.flush()
    del monkeypatch

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.awaiting_review_at is None
    scheduled = summary_scheduler_service.pop_project_todo_artifact_generations(db_session)
    assert len(scheduled) == 1
    [link] = list(
        (await db_session.execute(select(ProjectTodoArtifact))).scalars()
    )
    assert link.project_todo_id == todo.id
    artifact = scheduled[0]
    stored_artifact = await db_session.get(TerminalArtifact, artifact.artifact_id)
    assert stored_artifact is not None
    assert stored_artifact.status == TerminalArtifactStatus.pending
