from tests.unit.test_summary_scheduler_support import *

from app.contexts.workspace.application import summary_scheduler as summary_scheduler_service
from app.contexts.workspace.infrastructure.project_todos_repository import (
    complete_project_todos_after_artifact_status_change,
)
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus
from tests.unit.test_terminal_work_status_support import claude_completion_payload

@pytest.mark.asyncio
async def test_todo_moves_to_review_only_after_all_requested_artifacts_finish(db_session):
    window = await create_window(db_session)
    todo = ProjectTodo(
        client_id=window.client_id,
        project_path="/workspace/project",
        title="Finish all artifacts",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatched_at=datetime(2026, 5, 21, 11, 59, tzinfo=timezone.utc),
        artifact_kinds_json=["agent_trace_graph"],
    )
    db_session.add(todo)
    await db_session.flush()
    trace_artifact = TerminalArtifact(
        client_id=window.client_id,
        virtual_window_id=window.id,
        source_window_id=window.id,
        artifact_kind="agent_trace_graph",
        title="Trace",
        status=TerminalArtifactStatus.succeeded,
    )
    db_session.add(trace_artifact)
    await db_session.flush()
    db_session.add_all(
        [
            ProjectTodoArtifact(
                project_todo_id=todo.id,
                terminal_artifact_id=trace_artifact.id,
                created_by_window_id=window.id,
                purpose="todo_artifact",
            ),
        ]
    )
    await db_session.flush()

    await complete_project_todos_after_artifact_status_change(db_session, trace_artifact.id)

    assert todo.status == ProjectTodoStatus.awaiting_review
    assert todo.awaiting_review_at is not None
    assert todo.review_unseen is True

@pytest.mark.asyncio
async def test_agent_user_message_updates_window_user_input_projection(db_session):
    window = await create_window(db_session)
    user_input_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = await add_agent_event(
        db_session,
        window,
        user_input_at,
        fingerprint="agent-user-input-projection",
        kind="user_message",
    )

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert window.agent_activity_latest_at == user_input_at
    assert window.agent_activity_latest_user_input_at == user_input_at

@pytest.mark.asyncio
async def test_late_user_message_updates_projection_without_rewinding_activity(db_session):
    window = await create_window(db_session)
    output_at = datetime(2026, 5, 21, 12, 0, 10, tzinfo=timezone.utc)
    user_input_at = output_at - timedelta(seconds=5)
    window.agent_activity_latest_at = output_at
    event = await add_agent_event(
        db_session,
        window,
        user_input_at,
        fingerprint="late-agent-user-input-projection",
        kind="user_message",
    )

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert window.agent_activity_latest_at == output_at
    assert window.agent_activity_latest_user_input_at == user_input_at

@pytest.mark.asyncio
async def test_agent_session_meta_does_not_update_activity_state(db_session):
    window = await create_window(db_session)
    event_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    event = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="session_meta",
        virtual_window_id=window.id,
        payload_json={
            "provider": "codex",
            "raw_type": "session_meta",
            "payload": {"id": "codex-session-1"},
        },
        fingerprint="agent-session-meta-not-work",
        created_at=event_at,
    )
    db_session.add(event)
    await db_session.flush()

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is None
    assert window.agent_activity_latest_at is None
    assert window.agent_activity_latest_event_id is None


@pytest.mark.asyncio
async def test_claude_token_metric_does_not_update_activity_state_after_completion(db_session):
    window = await create_window(db_session)
    completed_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    metric_at = completed_at + timedelta(seconds=5)
    completion = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="assistant_message",
        virtual_window_id=window.id,
        payload_json=claude_completion_payload(),
        fingerprint="claude-completion-before-token-metric",
        created_at=completed_at,
    )
    metric = Event(
        client_id=window.client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="otel://claude-code/metrics",
        kind="otel_metric",
        virtual_window_id=window.id,
        payload_json={
            "provider": "claude_code",
            "type": "otel_metric",
            "name": "claude_code.token.usage",
            "attributes": {"session.id": "claude-session-1"},
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        },
        fingerprint="claude-token-metric-after-completion",
        created_at=metric_at,
    )
    db_session.add_all([completion, metric])
    await db_session.flush()

    completion_job = await schedule_summary_after_agent_activity(db_session, window, event=completion)
    metric_job = await schedule_summary_after_agent_activity(db_session, window, event=metric)

    assert completion_job is not None
    assert metric_job is None
    assert window.agent_activity_latest_at == completed_at
    assert window.agent_activity_latest_event_id == completion.id
    assert window.agent_activity_latest_completed_at == completed_at


@pytest.mark.asyncio
async def test_late_completion_updates_completion_state_without_rewinding_activity(db_session):
    window = await create_window(db_session)
    output_at = datetime(2026, 5, 21, 12, 0, 10, tzinfo=timezone.utc)
    completed_at = output_at - timedelta(seconds=10)
    window.agent_activity_latest_at = output_at
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
        fingerprint="agent-completion-window-state-late",
        created_at=output_at + timedelta(milliseconds=30),
    )
    db_session.add(event)
    await db_session.flush()

    await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert window.agent_activity_latest_at == output_at
    assert window.agent_activity_latest_completed_at == completed_at

@pytest.mark.asyncio
async def test_agent_user_message_after_agent_command_schedules_summary_after_idle(db_session):
    window = await create_window(db_session)
    command_at = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    user_message_at = command_at + timedelta(seconds=2)
    await add_agent_command_input(db_session, window, command_at, 1)
    event = await add_agent_event(db_session, window, user_message_at, fingerprint="agent-user-1", kind="user_message")

    job = await schedule_summary_after_agent_activity(db_session, window, event=event)

    assert job is not None
    assert job.status == SummaryJobStatus.pending
    assert job.run_after == user_message_at + timedelta(seconds=20)
    assert job.trigger_reason == AGENT_IDLE_REASON
