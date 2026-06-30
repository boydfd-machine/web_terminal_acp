from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.contexts.workspace.domain.project_todo_recurrence import (
    PROJECT_TODO_EXECUTION_PERIODIC,
    PROJECT_TODO_RUN_COMPLETED,
    PROJECT_TODO_RUN_DISPATCHED,
    PROJECT_TODO_RUN_FAILED,
    PROJECT_TODO_RUN_STARTING,
    PROJECT_TODO_TRIGGER_CRON,
    ProjectTodoSchedule,
    next_cron_trigger_after,
    project_todo_schedule_enabled,
    validate_project_todo_schedule,
)
from app.models import ProjectTodo, ProjectTodoRun, ProjectTodoStatus


def apply_project_todo_schedule(
    todo: ProjectTodo,
    schedule: ProjectTodoSchedule,
    *,
    now: datetime | None = None,
) -> None:
    validate_project_todo_schedule(schedule)
    current = now or datetime.now(UTC)
    cron_expression = schedule.cron_expression.strip() if schedule.cron_expression else None
    todo.execution_kind = schedule.execution_kind
    todo.terminal_policy = schedule.terminal_policy
    todo.trigger_strategy = schedule.trigger_strategy
    todo.cron_expression = cron_expression
    todo.schedule_enabled = project_todo_schedule_enabled(schedule)
    todo.next_trigger_at = (
        next_cron_trigger_after(cron_expression, current)
        if todo.schedule_enabled and cron_expression is not None
        else None
    )


async def create_project_todo_run(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    agent_launch_json: dict | None,
    dispatch_mode: str,
    prompt: str,
    trigger_reason: str,
    window_id: UUID | None = None,
    now: datetime | None = None,
) -> ProjectTodoRun:
    current = now or datetime.now(UTC)
    run_number = int(todo.execution_run_count or 0) + 1
    run = ProjectTodoRun(
        project_todo_id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        window_id=window_id,
        run_number=run_number,
        trigger_strategy=todo.trigger_strategy,
        trigger_reason=trigger_reason,
        terminal_policy=todo.terminal_policy,
        agent_launch_json=agent_launch_json,
        dispatch_mode=dispatch_mode,
        prompt=prompt,
        status=PROJECT_TODO_RUN_STARTING,
        started_at=current,
    )
    todo.execution_run_count = run_number
    todo.last_triggered_at = current
    todo.last_agent_launch_json = agent_launch_json
    todo.last_dispatch_mode = dispatch_mode
    if todo.trigger_strategy == PROJECT_TODO_TRIGGER_CRON:
        todo.next_trigger_at = None
    session.add(run)
    await session.flush()
    return run


async def mark_project_todo_run_window(
    session: AsyncSession,
    run_id: UUID,
    window_id: UUID,
) -> None:
    run = await session.get(ProjectTodoRun, run_id)
    if run is None:
        return
    run.window_id = window_id
    await session.flush()


async def mark_project_todo_run_dispatched(
    session: AsyncSession,
    run_id: UUID,
    *,
    window_id: UUID,
    dispatched_at: datetime | None = None,
) -> None:
    run = await session.get(ProjectTodoRun, run_id)
    if run is None:
        return
    run.window_id = window_id
    run.status = PROJECT_TODO_RUN_DISPATCHED
    run.dispatched_at = dispatched_at or datetime.now(UTC)
    run.last_error = None
    await session.flush()


async def mark_project_todo_run_failed(
    session: AsyncSession,
    todo: ProjectTodo,
    run_id: UUID | None,
    *,
    error: str,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    run = await session.get(ProjectTodoRun, run_id) if run_id is not None else None
    if run is not None:
        run.status = PROJECT_TODO_RUN_FAILED
        run.completed_at = current
        run.last_error = error
    _schedule_next_cron_cycle(todo, current)
    await session.flush()


async def schedule_next_project_todo_cron(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    now: datetime | None = None,
) -> None:
    _schedule_next_cron_cycle(todo, now or datetime.now(UTC))
    await session.flush()


async def complete_latest_project_todo_run_for_window(
    session: AsyncSession,
    todo: ProjectTodo,
    window_id: UUID,
    *,
    completed_at: datetime,
) -> ProjectTodoRun | None:
    run = await session.scalar(
        select(ProjectTodoRun)
        .where(
            ProjectTodoRun.project_todo_id == todo.id,
            ProjectTodoRun.window_id == window_id,
            ProjectTodoRun.status.in_([PROJECT_TODO_RUN_STARTING, PROJECT_TODO_RUN_DISPATCHED]),
        )
        .order_by(desc(ProjectTodoRun.run_number), desc(ProjectTodoRun.created_at), desc(ProjectTodoRun.id))
        .limit(1)
    )
    if run is None:
        return None
    run.status = PROJECT_TODO_RUN_COMPLETED
    run.completed_at = completed_at
    run.last_error = None
    _schedule_next_cron_cycle(todo, completed_at)
    await session.flush()
    return run


async def list_recent_project_todo_runs_for_todos(
    session: AsyncSession,
    todo_ids: list[UUID],
    *,
    limit_per_todo: int = 12,
) -> dict[UUID, list[ProjectTodoRun]]:
    if not todo_ids:
        return {}
    ranked = (
        select(
            ProjectTodoRun,
            func.row_number()
            .over(
                partition_by=ProjectTodoRun.project_todo_id,
                order_by=(desc(ProjectTodoRun.created_at), desc(ProjectTodoRun.id)),
            )
            .label("run_rank"),
        )
        .where(ProjectTodoRun.project_todo_id.in_(todo_ids))
        .subquery()
    )
    run_alias = aliased(ProjectTodoRun, ranked)
    rows = list(
        await session.scalars(
            select(run_alias)
            .where(ranked.c.run_rank <= limit_per_todo)
            .order_by(run_alias.project_todo_id, desc(run_alias.created_at), desc(run_alias.id))
        )
    )
    grouped: dict[UUID, list[ProjectTodoRun]] = {}
    for run in rows:
        grouped.setdefault(run.project_todo_id, []).append(run)
    return grouped


async def due_cron_project_todos(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> list[ProjectTodo]:
    current = now or datetime.now(UTC)
    return list(
        await session.scalars(
            select(ProjectTodo)
            .where(
                ProjectTodo.execution_kind == PROJECT_TODO_EXECUTION_PERIODIC,
                ProjectTodo.trigger_strategy == PROJECT_TODO_TRIGGER_CRON,
                ProjectTodo.schedule_enabled.is_(True),
                ProjectTodo.status == ProjectTodoStatus.todo,
                ProjectTodo.next_trigger_at.is_not(None),
                ProjectTodo.next_trigger_at <= current,
            )
            .order_by(ProjectTodo.next_trigger_at, ProjectTodo.id)
            .limit(limit)
        )
    )


def project_todo_schedule_from_model(todo: ProjectTodo) -> ProjectTodoSchedule:
    return ProjectTodoSchedule(
        execution_kind=todo.execution_kind,
        terminal_policy=todo.terminal_policy,
        trigger_strategy=todo.trigger_strategy,
        cron_expression=todo.cron_expression,
        schedule_enabled=todo.schedule_enabled,
    )


def _schedule_next_cron_cycle(todo: ProjectTodo, current: datetime) -> None:
    if (
        todo.execution_kind == PROJECT_TODO_EXECUTION_PERIODIC
        and todo.trigger_strategy == PROJECT_TODO_TRIGGER_CRON
        and todo.schedule_enabled
        and todo.cron_expression
    ):
        todo.next_trigger_at = next_cron_trigger_after(todo.cron_expression, current)
    else:
        todo.next_trigger_at = None
