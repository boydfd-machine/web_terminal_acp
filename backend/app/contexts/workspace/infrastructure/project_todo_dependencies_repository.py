from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectTodo, ProjectTodoDependency, ProjectTodoQueuedDispatch, ProjectTodoStatus
from app.platform.common_schemas import AgentLaunchIn

DEPENDENCY_SATISFIED_STATUSES = (ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done)


class ProjectTodoDependencyError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectTodoRelationSummary:
    id: UUID
    title: str
    status: ProjectTodoStatus
    completed_at: datetime | None


@dataclass(frozen=True)
class ProjectTodoDependencyGraph:
    dependencies: dict[UUID, list[ProjectTodoRelationSummary]]
    dependents: dict[UUID, list[ProjectTodoRelationSummary]]
    queued_dispatches: set[UUID]


@dataclass(frozen=True)
class QueuedProjectTodoDispatch:
    todo: ProjectTodo
    agent_launch: AgentLaunchIn
    dispatch_mode: str
    prompt: str


async def dependency_graph_for_todos(
    session: AsyncSession,
    todo_ids: list[UUID],
) -> ProjectTodoDependencyGraph:
    if not todo_ids:
        return ProjectTodoDependencyGraph({}, {}, set())

    dependency_rows = list(
        await session.execute(
            select(ProjectTodoDependency, ProjectTodo)
            .join(ProjectTodo, ProjectTodo.id == ProjectTodoDependency.depends_on_todo_id)
            .where(ProjectTodoDependency.project_todo_id.in_(todo_ids))
            .order_by(ProjectTodo.sort_order, ProjectTodo.updated_at, ProjectTodo.id)
        )
    )
    dependent_rows = list(
        await session.execute(
            select(ProjectTodoDependency, ProjectTodo)
            .join(ProjectTodo, ProjectTodo.id == ProjectTodoDependency.project_todo_id)
            .where(ProjectTodoDependency.depends_on_todo_id.in_(todo_ids))
            .order_by(ProjectTodo.sort_order, ProjectTodo.updated_at, ProjectTodo.id)
        )
    )
    queued = set(
        await session.scalars(
            select(ProjectTodoQueuedDispatch.project_todo_id).where(ProjectTodoQueuedDispatch.project_todo_id.in_(todo_ids))
        )
    )

    dependencies: dict[UUID, list[ProjectTodoRelationSummary]] = {}
    dependents: dict[UUID, list[ProjectTodoRelationSummary]] = {}
    for edge, upstream in dependency_rows:
        dependencies.setdefault(edge.project_todo_id, []).append(_summary(upstream))
    for edge, downstream in dependent_rows:
        dependents.setdefault(edge.depends_on_todo_id, []).append(_summary(downstream))
    return ProjectTodoDependencyGraph(dependencies, dependents, queued)


async def queued_project_todo_ids(
    session: AsyncSession,
    todo_ids: list[UUID],
) -> set[UUID]:
    if not todo_ids:
        return set()
    return set(
        await session.scalars(
            select(ProjectTodoQueuedDispatch.project_todo_id).where(ProjectTodoQueuedDispatch.project_todo_id.in_(todo_ids))
        )
    )


async def set_project_todo_dependencies(
    session: AsyncSession,
    todo: ProjectTodo,
    dependency_ids: list[UUID],
) -> None:
    unique_ids = list(dict.fromkeys(dependency_ids))
    if todo.id in unique_ids:
        raise ProjectTodoDependencyError("todo cannot depend on itself")
    dependencies = list(
        await session.scalars(
            select(ProjectTodo).where(
                ProjectTodo.id.in_(unique_ids),
                ProjectTodo.client_id == todo.client_id,
                ProjectTodo.project_path == todo.project_path,
            )
        )
    ) if unique_ids else []
    if len(dependencies) != len(unique_ids):
        raise ProjectTodoDependencyError("dependency todo not found in this project")

    for dependency_id in unique_ids:
        if await _path_exists(session, start_todo_id=dependency_id, target_todo_id=todo.id):
            raise ProjectTodoDependencyError("dependency would create a cycle")

    await session.execute(delete(ProjectTodoDependency).where(ProjectTodoDependency.project_todo_id == todo.id))
    for dependency_id in unique_ids:
        session.add(
            ProjectTodoDependency(
                client_id=todo.client_id,
                project_path=todo.project_path,
                project_todo_id=todo.id,
                depends_on_todo_id=dependency_id,
            )
        )
    await session.flush()


async def has_incomplete_dependencies(session: AsyncSession, todo_id: UUID) -> bool:
    return await session.scalar(
        select(ProjectTodoDependency.id)
        .join(ProjectTodo, ProjectTodo.id == ProjectTodoDependency.depends_on_todo_id)
        .where(
            ProjectTodoDependency.project_todo_id == todo_id,
            ~ProjectTodo.status.in_(DEPENDENCY_SATISFIED_STATUSES),
        )
        .limit(1)
    ) is not None


async def queue_project_todo_dispatch(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    agent_launch: AgentLaunchIn,
    dispatch_mode: str,
    prompt: str,
) -> ProjectTodoQueuedDispatch:
    queued = await session.scalar(
        select(ProjectTodoQueuedDispatch).where(ProjectTodoQueuedDispatch.project_todo_id == todo.id)
    )
    now = datetime.now(UTC)
    if queued is None:
        queued = ProjectTodoQueuedDispatch(
            project_todo_id=todo.id,
            client_id=todo.client_id,
            project_path=todo.project_path,
            agent_launch_json=agent_launch.model_dump(mode="json"),
            dispatch_mode=dispatch_mode,
            prompt=prompt,
            queued_at=now,
        )
        session.add(queued)
    else:
        queued.agent_launch_json = agent_launch.model_dump(mode="json")
        queued.dispatch_mode = dispatch_mode
        queued.prompt = prompt
        queued.updated_at = now
    await session.flush()
    return queued


async def clear_project_todo_queued_dispatch(session: AsyncSession, todo_id: UUID) -> None:
    await session.execute(delete(ProjectTodoQueuedDispatch).where(ProjectTodoQueuedDispatch.project_todo_id == todo_id))
    await session.flush()


async def ready_queued_dispatches_for_upstream(
    session: AsyncSession,
    upstream_todo_id: UUID,
) -> list[QueuedProjectTodoDispatch]:
    rows = list(
        await session.execute(
            select(ProjectTodo, ProjectTodoQueuedDispatch)
            .join(ProjectTodoDependency, ProjectTodoDependency.project_todo_id == ProjectTodo.id)
            .join(ProjectTodoQueuedDispatch, ProjectTodoQueuedDispatch.project_todo_id == ProjectTodo.id)
            .where(
                ProjectTodoDependency.depends_on_todo_id == upstream_todo_id,
                ProjectTodo.status == ProjectTodoStatus.todo,
            )
            .order_by(ProjectTodoQueuedDispatch.queued_at, ProjectTodoQueuedDispatch.id)
        )
    )
    ready: list[QueuedProjectTodoDispatch] = []
    for todo, queued in rows:
        if await has_incomplete_dependencies(session, todo.id):
            continue
        ready.append(
            QueuedProjectTodoDispatch(
                todo=todo,
                agent_launch=AgentLaunchIn.model_validate(queued.agent_launch_json),
                dispatch_mode=queued.dispatch_mode,
                prompt=queued.prompt,
            )
        )
    return ready


async def ready_queued_dispatches_for_project(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_path: str,
) -> list[QueuedProjectTodoDispatch]:
    rows = list(
        await session.execute(
            select(ProjectTodo, ProjectTodoQueuedDispatch)
            .join(ProjectTodoQueuedDispatch, ProjectTodoQueuedDispatch.project_todo_id == ProjectTodo.id)
            .where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.project_path == project_path,
                ProjectTodo.status == ProjectTodoStatus.todo,
            )
            .order_by(ProjectTodoQueuedDispatch.queued_at, ProjectTodoQueuedDispatch.id)
        )
    )
    ready: list[QueuedProjectTodoDispatch] = []
    for todo, queued in rows:
        if await has_incomplete_dependencies(session, todo.id):
            continue
        ready.append(
            QueuedProjectTodoDispatch(
                todo=todo,
                agent_launch=AgentLaunchIn.model_validate(queued.agent_launch_json),
                dispatch_mode=queued.dispatch_mode,
                prompt=queued.prompt,
            )
        )
    return ready


def _summary(todo: ProjectTodo) -> ProjectTodoRelationSummary:
    return ProjectTodoRelationSummary(
        id=todo.id,
        title=todo.title,
        status=todo.status,
        completed_at=todo.completed_at,
    )


async def _path_exists(session: AsyncSession, *, start_todo_id: UUID, target_todo_id: UUID) -> bool:
    stack = [start_todo_id]
    seen: set[UUID] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        if current == target_todo_id:
            return True
        upstream_ids = list(
            await session.scalars(
                select(ProjectTodoDependency.depends_on_todo_id)
                .where(ProjectTodoDependency.project_todo_id == current)
            )
        )
        stack.extend(upstream_id for upstream_id in upstream_ids if upstream_id not in seen)
    return False
