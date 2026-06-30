from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.workspace.domain.project_todo_recurrence import (
    PROJECT_TODO_RUN_DISPATCHED,
    PROJECT_TODO_RUN_STARTING,
)
from app.contexts.workspace.application.project_todo_background_completion import (
    background_work_waiting_error,
    final_completion_waiting_error,
)
from app.contexts.workspace.infrastructure.project_todos_repository import list_project_todos
from app.config import get_settings
from app.model_base import Base
from app.models import (
    Client,
    ClientRuntime,
    ClientStatus,
    ProjectTodo,
    ProjectTodoRun,
    ProjectTodoStatus,
    VirtualWindow,
    WindowStatus,
)


PROJECT_PATH = "/repo"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_project_todos_recovers_terminal_ready_dispatch_with_agent_input(db_session) -> None:
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    todo = _terminal_ready_todo(client, window, updated_at=base_time)
    run = _starting_run(
        client,
        todo,
        window,
        started_at=base_time + timedelta(seconds=10),
    )
    db_session.add_all([client, window, todo, run])
    await db_session.flush()

    todos = await list_project_todos(db_session, client.id, PROJECT_PATH)

    assert todos == [todo]
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage is None
    assert todo.dispatch_error is None
    assert todo.dispatched_at == window.agent_activity_latest_user_input_at
    assert run.status == PROJECT_TODO_RUN_DISPATCHED
    assert run.dispatched_at == window.agent_activity_latest_user_input_at
    assert run.last_error is None


@pytest.mark.asyncio
async def test_list_project_todos_recovers_terminal_ready_comment_without_run(db_session) -> None:
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    todo = _terminal_ready_todo(client, window, updated_at=base_time)
    db_session.add_all([client, window, todo])
    await db_session.flush()

    await list_project_todos(db_session, client.id, PROJECT_PATH)

    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage is None
    assert todo.dispatched_at == window.agent_activity_latest_user_input_at


@pytest.mark.asyncio
async def test_list_project_todos_keeps_stale_agent_input_in_terminal_ready(db_session) -> None:
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=5),
    )
    todo = _terminal_ready_todo(client, window, updated_at=base_time)
    run = _starting_run(
        client,
        todo,
        window,
        started_at=base_time + timedelta(seconds=10),
    )
    db_session.add_all([client, window, todo, run])
    await db_session.flush()

    await list_project_todos(db_session, client.id, PROJECT_PATH)

    assert todo.status == ProjectTodoStatus.todo
    assert todo.dispatch_stage == "TERMINAL_READY"
    assert todo.dispatched_at is None
    assert run.status == PROJECT_TODO_RUN_STARTING
    assert run.dispatched_at is None


@pytest.mark.asyncio
async def test_list_project_todos_does_not_bypass_completion_verification(db_session, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    window.agent_activity_latest_completed_at = base_time + timedelta(minutes=2)
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path=PROJECT_PATH,
        title="Background task should wait",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
        assigned_window_id=window.id,
        assigned_agent="claude",
        dispatch_prompt="Start background sleep and report later",
        dispatched_at=base_time + timedelta(seconds=20),
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    scheduled = []

    def schedule_verification(todo_to_verify: ProjectTodo, completed_at: datetime) -> bool:
        scheduled.append((todo_to_verify.id, completed_at))
        return True

    todos = await list_project_todos(
        db_session,
        client.id,
        PROJECT_PATH,
        verification_scheduler=schedule_verification,
    )

    assert todos == [todo]
    assert scheduled == [(todo.id, window.agent_activity_latest_completed_at)]
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.awaiting_review_at is None


@pytest.mark.asyncio
async def test_list_project_todos_recovers_background_completion_verification_after_restart(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    completed_at = base_time + timedelta(minutes=2)
    window.agent_activity_latest_completed_at = completed_at
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path=PROJECT_PATH,
        title="Background task should recover verifier",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
        assigned_window_id=window.id,
        assigned_agent="claude",
        dispatch_prompt="Start background sleep and report later",
        dispatched_at=base_time + timedelta(seconds=20),
        dispatch_stage="verifying",
        dispatch_error=background_work_waiting_error(["sleep 120"]),
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    scheduled = []

    def schedule_verification(todo_to_verify: ProjectTodo, actual_completed_at: datetime) -> bool:
        scheduled.append((todo_to_verify.id, actual_completed_at))
        return True

    await list_project_todos(
        db_session,
        client.id,
        PROJECT_PATH,
        verification_scheduler=schedule_verification,
    )

    assert scheduled == [(todo.id, completed_at)]
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.awaiting_review_at is None


@pytest.mark.asyncio
async def test_list_project_todos_recovers_final_completion_wait_after_restart(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    completed_at = base_time + timedelta(minutes=2)
    window.agent_activity_latest_completed_at = completed_at
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path=PROJECT_PATH,
        title="Background task should recover final wait",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
        assigned_window_id=window.id,
        assigned_agent="claude",
        dispatch_prompt="Start background sleep and report later",
        dispatched_at=base_time + timedelta(seconds=20),
        dispatch_stage="verifying",
        dispatch_error=final_completion_waiting_error(completed_at),
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    scheduled = []

    def schedule_verification(todo_to_verify: ProjectTodo, actual_completed_at: datetime) -> bool:
        scheduled.append((todo_to_verify.id, actual_completed_at))
        return True

    await list_project_todos(
        db_session,
        client.id,
        PROJECT_PATH,
        verification_scheduler=schedule_verification,
    )

    assert scheduled == [(todo.id, completed_at)]
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.awaiting_review_at is None


@pytest.mark.asyncio
async def test_list_project_todos_keeps_unclassified_verifying_without_reschedule(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", True)
    base_time = datetime(2026, 6, 6, 13, 51, tzinfo=UTC)
    client, window = _client_and_window(
        user_input_at=base_time + timedelta(seconds=15),
    )
    window.agent_activity_latest_completed_at = base_time + timedelta(minutes=2)
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path=PROJECT_PATH,
        title="Normal verifier remains in flight",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
        assigned_window_id=window.id,
        assigned_agent="claude",
        dispatch_prompt="Run a normal task",
        dispatched_at=base_time + timedelta(seconds=20),
        dispatch_stage="verifying",
        dispatch_error="verification attempt 1 incomplete: still running tests",
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    scheduled = []

    def schedule_verification(todo_to_verify: ProjectTodo, actual_completed_at: datetime) -> bool:
        scheduled.append((todo_to_verify.id, actual_completed_at))
        return True

    await list_project_todos(
        db_session,
        client.id,
        PROJECT_PATH,
        verification_scheduler=schedule_verification,
    )

    assert scheduled == []
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.awaiting_review_at is None


def _client_and_window(*, user_input_at: datetime) -> tuple[Client, VirtualWindow]:
    client = Client(
        id=uuid4(),
        name=f"remote-{uuid4()}",
        token_hash="hash",
        status=ClientStatus.ONLINE,
        runtime=ClientRuntime.remote,
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Todo worker",
        status=WindowStatus.active,
        cwd=PROJECT_PATH,
        shell_command="codex",
        agent_activity_latest_user_input_at=user_input_at,
    )
    return client, window


def _terminal_ready_todo(client: Client, window: VirtualWindow, *, updated_at: datetime) -> ProjectTodo:
    return ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path=PROJECT_PATH,
        title="Recover stuck dispatch",
        status=ProjectTodoStatus.todo,
        sort_order=1,
        assigned_window_id=window.id,
        assigned_agent="codex",
        dispatch_prompt="Todo prompt",
        dispatch_stage="TERMINAL_READY",
        updated_at=updated_at,
    )


def _starting_run(
    client: Client,
    todo: ProjectTodo,
    window: VirtualWindow,
    *,
    started_at: datetime,
) -> ProjectTodoRun:
    return ProjectTodoRun(
        project_todo_id=todo.id,
        client_id=client.id,
        project_path=PROJECT_PATH,
        window_id=window.id,
        run_number=1,
        trigger_strategy="MANUAL",
        trigger_reason="manual",
        terminal_policy="NEW_TERMINAL",
        agent_launch_json={"agent": "codex"},
        dispatch_mode="submit",
        prompt="Todo prompt",
        status=PROJECT_TODO_RUN_STARTING,
        started_at=started_at,
    )
