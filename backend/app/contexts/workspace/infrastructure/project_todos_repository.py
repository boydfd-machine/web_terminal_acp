from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.domain.project_todo_recurrence import ProjectTodoSchedule
from app.contexts.workspace.infrastructure.project_todo_artifacts_repository import (
    complete_project_todos_after_artifact_status_change as complete_project_todos_after_artifact_status_change,
    list_project_todo_artifacts as list_project_todo_artifacts,
    project_todo_has_incomplete_requested_artifacts as project_todo_has_incomplete_requested_artifacts,
)
from app.models import (
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoDependency,
    ProjectTodoQueuedDispatch,
    ProjectTodoStatus,
    TerminalArtifact,
    VirtualWindow,
)
from app.contexts.workspace.application.project_todo_artifacts import (
    ProjectTodoArtifactGeneration,
    queue_project_todo_artifact_generations,
)
from app.contexts.workspace.application.project_todo_background_completion import todo_waited_for_background_work
from app.contexts.workspace.application.project_todo_completion_background_gate import (
    final_completion_wait_started_at,
)
from app.contexts.workspace.infrastructure.project_todo_reviews_repository import (
    apply_manual_review_status_to_latest_run,
    latest_project_todo_review_run,
    mark_running_review_run_completed_without_verdict,
)
from app.contexts.workspace.infrastructure.project_todo_runs_repository import apply_project_todo_schedule
from app.contexts.workspace.infrastructure.project_todo_list_queries import list_project_todos_for_project
from app.contexts.workspace.infrastructure.project_todo_dispatch_recovery_repository import (
    sync_started_project_todo_dispatches,
)
from app.contexts.workspace.infrastructure.project_todo_types_repository import (
    DEFAULT_PROJECT_TODO_TYPE_ID,
    get_project_todo_type,
)
from app.contexts.workspace.infrastructure.project_todo_completion_repository import (
    _mark_implementation_awaiting_review,
    _mark_implementation_completed,
)
from app.contexts.workspace.infrastructure.project_todo_reference_resolver import (
    referenced_project_todos_for_todos as referenced_project_todos_for_todos,
)
from app.contexts.workspace.infrastructure.project_todo_sort_repository import next_project_todo_sort_order


async def sync_dispatched_project_todos(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    remote_client_available: Callable[[UUID], bool] | None = None,
    verification_scheduler: Callable[[ProjectTodo, datetime], bool] | None = None,
) -> tuple[bool, list[ProjectTodoArtifactGeneration]]:
    rows = list(
        await session.execute(
            select(ProjectTodo)
            .add_columns(VirtualWindow.agent_activity_latest_completed_at)
            .join(VirtualWindow, VirtualWindow.id == ProjectTodo.assigned_window_id)
            .where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.project_path == project_path,
                ProjectTodo.status == ProjectTodoStatus.dispatched,
                VirtualWindow.agent_activity_latest_completed_at.is_not(None),
            )
        )
    )
    changed = False
    generations: list[ProjectTodoArtifactGeneration] = []
    for todo, completed_at in rows:
        completed_at = _ensure_aware(completed_at)
        if todo.dispatched_at is not None and completed_at < _ensure_aware(todo.dispatched_at):
            continue
        if todo.dispatch_stage == "verifying" and not todo_waited_for_background_work(todo.dispatch_error):
            continue
        verification_completed_at = final_completion_wait_started_at(todo.dispatch_error) or completed_at
        if verification_scheduler is not None and verification_scheduler(todo, verification_completed_at):
            todo.dispatch_stage = "verifying"
            changed = True
            continue
        generations.extend(
            await _mark_implementation_completed(
                session,
                todo,
                completed_at,
                todo.assigned_window_id,
                remote_client_available=remote_client_available,
            )
        )
        changed = True
    if changed:
        await session.flush()
    return changed, generations


async def sync_project_todos_for_completed_window(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    completed_at: datetime,
    *,
    remote_client_available: Callable[[UUID], bool] | None = None,
    verification_scheduler: Callable[[ProjectTodo, datetime], bool] | None = None,
) -> tuple[bool, list[ProjectTodoArtifactGeneration]]:
    completed_at = _ensure_aware(completed_at)
    todos = list(
        await session.scalars(
            select(ProjectTodo).where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.assigned_window_id == window_id,
                ProjectTodo.status == ProjectTodoStatus.dispatched,
            )
        )
    )
    changed = False
    generations: list[ProjectTodoArtifactGeneration] = []
    for todo in todos:
        if todo.dispatched_at is not None and completed_at < _ensure_aware(todo.dispatched_at):
            continue
        if todo.dispatch_stage == "verifying" and not todo_waited_for_background_work(todo.dispatch_error):
            continue
        verification_completed_at = final_completion_wait_started_at(todo.dispatch_error) or completed_at
        if verification_scheduler is not None and verification_scheduler(todo, verification_completed_at):
            todo.dispatch_stage = "verifying"
            changed = True
            continue
        generations.extend(
            await _mark_implementation_completed(
                session,
                todo,
                completed_at,
                window_id,
                remote_client_available=remote_client_available,
            )
        )
        changed = True
    review_todos = list(
        await session.scalars(
            select(ProjectTodo).where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.review_window_id == window_id,
                ProjectTodo.review_status == "RUNNING",
            )
        )
    )
    for todo in review_todos:
        if todo.review_dispatched_at is not None and completed_at < _ensure_aware(todo.review_dispatched_at):
            continue
        await mark_running_review_run_completed_without_verdict(
            session,
            window_id=window_id,
            completed_at=completed_at,
        )
        todo.review_status = "REVIEWED"
        todo.reviewed_at = completed_at
        changed = True
    if changed:
        await session.flush()
    return changed, generations


async def list_project_todos(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    updated_at_start: datetime | None = None,
    updated_at_end: datetime | None = None,
    remote_client_available: Callable[[UUID], bool] | None = None,
    verification_scheduler: Callable[[ProjectTodo, datetime], bool] | None = None,
) -> list[ProjectTodo]:
    await sync_started_project_todo_dispatches(session, client_id, project_path)
    _changed, generations = await sync_dispatched_project_todos(
        session,
        client_id,
        project_path,
        remote_client_available=remote_client_available,
        verification_scheduler=verification_scheduler,
    )
    queue_project_todo_artifact_generations(session, generations)
    return await list_project_todos_for_project(
        session,
        client_id,
        project_path,
        updated_at_start=updated_at_start,
        updated_at_end=updated_at_end,
    )


async def assigned_project_todo_titles_by_window(
    session: AsyncSession,
    window_ids: list[UUID],
    *,
    client_id: UUID | None = None,
) -> dict[UUID, str]:
    if not window_ids:
        return {}

    stmt = (
        select(ProjectTodo.assigned_window_id, ProjectTodo.title)
        .where(ProjectTodo.assigned_window_id.in_(window_ids))
        .order_by(desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
    )
    if client_id is not None:
        stmt = stmt.where(ProjectTodo.client_id == client_id)

    rows = await session.execute(stmt)
    titles: dict[UUID, str] = {}
    for window_id, title in rows:
        if window_id is not None:
            titles.setdefault(window_id, title)
    return titles


async def create_project_todo(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    title: str,
    description: str | None,
    status: ProjectTodoStatus,
    parent_todo_id: UUID | None = None,
    todo_type_id: str = DEFAULT_PROJECT_TODO_TYPE_ID,
    review_strategy: str = "LOCAL_CARD",
    review_agent: str | None = None,
    review_agent_profile_id: str | None = None,
    schedule: ProjectTodoSchedule | None = None,
    artifact_kinds: list[str] | None = None,
    input_artifact_ids: list[str] | None = None,
    artifact_model_selection: dict[str, Any] | None = None,
) -> ProjectTodo:
    todo_type = await get_project_todo_type(session, client_id, project_path, todo_type_id)
    if todo_type is None:
        raise ValueError("todo type not found")
    parent_todo = None
    if parent_todo_id is not None:
        parent_todo = await get_project_todo(session, client_id, project_path, parent_todo_id)
        if parent_todo is None:
            raise ValueError("parent todo not found")
    sort_order = await next_project_todo_sort_order(session, client_id, project_path)
    resolved_artifact_kinds = todo_type.artifact_kinds_json if artifact_kinds is None else artifact_kinds
    resolved_input_artifact_ids = todo_type.input_artifact_ids_json if input_artifact_ids is None else input_artifact_ids
    todo = ProjectTodo(
        client_id=client_id,
        project_path=project_path,
        parent_todo_id=parent_todo.id if parent_todo is not None else None,
        todo_type_id=todo_type.id,
        title=title,
        description=description,
        status=status,
        sort_order=sort_order,
        assigned_agent=todo_type.agent,
        agent_profile_id=todo_type.agent_profile_id,
        review_strategy=review_strategy,
        review_agent=review_agent,
        review_agent_profile_id=review_agent_profile_id,
        artifact_kinds_json=resolved_artifact_kinds or None,
        input_artifact_ids_json=resolved_input_artifact_ids or None,
        artifact_model_selection_json=artifact_model_selection,
    )
    if schedule is not None:
        apply_project_todo_schedule(todo, schedule)
    session.add(todo)
    await session.flush()
    return todo


async def get_project_todo(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
) -> ProjectTodo | None:
    return await session.scalar(
        select(ProjectTodo).where(
            ProjectTodo.id == todo_id,
            ProjectTodo.client_id == client_id,
            ProjectTodo.project_path == project_path,
        )
    )


async def project_todo_can_move_project(session: AsyncSession, todo: ProjectTodo) -> bool:
    if todo.status != ProjectTodoStatus.todo:
        return False
    queued_id = await session.scalar(
        select(ProjectTodoQueuedDispatch.id).where(ProjectTodoQueuedDispatch.project_todo_id == todo.id)
    )
    return queued_id is None


async def move_project_todo_to_project(
    session: AsyncSession,
    todo: ProjectTodo,
    target_project_path: str,
) -> ProjectTodo:
    if todo.project_path == target_project_path:
        return todo

    next_sort_order = await next_project_todo_sort_order(session, todo.client_id, target_project_path)
    target_todo_type = await get_project_todo_type(session, todo.client_id, target_project_path, todo.todo_type_id)

    await session.execute(
        update(ProjectTodo)
        .where(ProjectTodo.parent_todo_id == todo.id)
        .values(parent_todo_id=None)
    )
    await session.execute(
        delete(ProjectTodoDependency).where(
            or_(
                ProjectTodoDependency.project_todo_id == todo.id,
                ProjectTodoDependency.depends_on_todo_id == todo.id,
            )
        )
    )
    await session.execute(
        delete(ProjectTodoQueuedDispatch).where(ProjectTodoQueuedDispatch.project_todo_id == todo.id)
    )

    todo.parent_todo_id = None
    todo.project_path = target_project_path
    todo.sort_order = next_sort_order
    if target_todo_type is None:
        todo.todo_type_id = DEFAULT_PROJECT_TODO_TYPE_ID
    await session.flush()
    return todo


async def resolve_project_todo_parent(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
    parent_todo_id: UUID | None,
) -> UUID | None:
    if parent_todo_id is None:
        return None
    if parent_todo_id == todo_id:
        raise ValueError("parent todo cannot be self")
    parent_todo = await get_project_todo(session, client_id, project_path, parent_todo_id)
    if parent_todo is None:
        raise ValueError("parent todo not found")
    if await _project_todo_parent_would_cycle(session, todo_id, parent_todo):
        raise ValueError("parent todo would create a cycle")
    return parent_todo.id


async def _project_todo_parent_would_cycle(
    session: AsyncSession,
    todo_id: UUID,
    parent_todo: ProjectTodo,
) -> bool:
    seen_ids = {todo_id}
    current = parent_todo
    while current.parent_todo_id is not None and current.parent_todo_id not in seen_ids:
        seen_ids.add(current.id)
        current = await session.get(ProjectTodo, current.parent_todo_id)
        if current is None:
            return False
    return current.parent_todo_id == todo_id


async def parent_project_todos_for_todos(
    session: AsyncSession,
    todos: list[ProjectTodo],
) -> dict[UUID, ProjectTodo]:
    parent_ids = {todo.parent_todo_id for todo in todos if todo.parent_todo_id is not None}
    if not parent_ids:
        return {}
    parents = list(await session.scalars(select(ProjectTodo).where(ProjectTodo.id.in_(parent_ids))))
    return {parent.id: parent for parent in parents}


def apply_project_todo_status(todo: ProjectTodo, status: ProjectTodoStatus, now: datetime | None = None) -> None:
    current = now or datetime.now(UTC)
    todo.status = status
    if status == ProjectTodoStatus.todo:
        _reset_project_todo_to_todo_state(todo)
    if status == ProjectTodoStatus.awaiting_review and todo.awaiting_review_at is None:
        todo.awaiting_review_at = current
    if status != ProjectTodoStatus.awaiting_review:
        todo.review_unseen = False
    if status == ProjectTodoStatus.done and todo.completed_at is None:
        todo.completed_at = current


def _reset_project_todo_to_todo_state(todo: ProjectTodo) -> None:
    todo.dispatch_stage = None
    todo.dispatch_error = None
    todo.dispatched_at = None
    todo.awaiting_review_at = None
    todo.completed_at = None
    todo.review_status = "NOT_REQUESTED"
    todo.review_window_id = None
    todo.review_prompt = None
    todo.review_dispatched_at = None
    todo.reviewed_at = None
    todo.review_unseen = False
    todo.needs_human_review = False
    todo.implementation_worktree_json = None


async def link_project_todo_artifact(
    session: AsyncSession,
    todo: ProjectTodo,
    artifact_id: UUID,
    *,
    purpose: str,
) -> ProjectTodoArtifact | None:
    artifact = await session.scalar(
        select(TerminalArtifact).where(
            TerminalArtifact.id == artifact_id,
            TerminalArtifact.client_id == todo.client_id,
        )
    )
    if artifact is None:
        return None
    review_run = await latest_project_todo_review_run(session, todo.id)
    review_run_id = (
        review_run.id
        if review_run is not None
        and todo.review_window_id is not None
        and artifact.virtual_window_id == todo.review_window_id
        else None
    )
    existing = await session.scalar(
        select(ProjectTodoArtifact).where(
            ProjectTodoArtifact.project_todo_id == todo.id,
            ProjectTodoArtifact.terminal_artifact_id == artifact_id,
        )
    )
    if existing is not None:
        existing.purpose = purpose
        existing.review_run_id = review_run_id
        existing.created_by_window_id = artifact.virtual_window_id
        await session.flush()
        return existing
    link = ProjectTodoArtifact(
        project_todo_id=todo.id,
        terminal_artifact_id=artifact_id,
        review_run_id=review_run_id,
        created_by_window_id=artifact.virtual_window_id,
        purpose=purpose,
    )
    session.add(link)
    await session.flush()
    return link


async def apply_project_todo_review_status(
    session: AsyncSession,
    todo: ProjectTodo,
    review_status: str,
    *,
    reviewed_at: datetime | None = None,
) -> None:
    completed_at = reviewed_at or datetime.now(UTC)
    todo.review_status = review_status
    if review_status in {"APPROVED", "CHANGES_REQUESTED", "NEEDS_HUMAN_REVIEW"}:
        todo.reviewed_at = completed_at
    todo.needs_human_review = review_status == "NEEDS_HUMAN_REVIEW"
    await apply_manual_review_status_to_latest_run(
        session,
        todo,
        review_status=review_status,
        completed_at=completed_at,
    )


async def delete_project_todo(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
) -> bool:
    todo = await get_project_todo(session, client_id, project_path, todo_id)
    if todo is None:
        return False
    await session.delete(todo)
    await session.flush()
    return True


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
