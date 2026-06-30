from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.api.schemas import (
    ProjectTodoSearchMatchOut,
    ProjectTodoSearchOut,
    ProjectTodoSearchResultOut,
)
from app.models import ProjectTodo


async def search_project_todos(
    session: AsyncSession,
    *,
    client_id: UUID,
    query: str,
    project_path: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> ProjectTodoSearchOut:
    normalized_query = query.strip()
    if not normalized_query:
        return ProjectTodoSearchOut(
            query=normalized_query,
            results=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
        )

    like_query = f"%{_escape_like(normalized_query).lower()}%"
    filters = [
        ProjectTodo.client_id == client_id,
        or_(
            func.lower(ProjectTodo.title).like(like_query, escape="\\"),
            func.lower(ProjectTodo.project_path).like(like_query, escape="\\"),
            func.lower(cast(ProjectTodo.status, Text)).like(like_query, escape="\\"),
            func.lower(func.coalesce(ProjectTodo.description, "")).like(like_query, escape="\\"),
            func.lower(func.coalesce(ProjectTodo.assigned_agent, "")).like(like_query, escape="\\"),
        ),
    ]
    if project_path is not None:
        filters.append(ProjectTodo.project_path == project_path)
    total = (await session.scalar(select(func.count()).select_from(ProjectTodo).where(*filters))) or 0
    todos = list(
        await session.scalars(
            select(ProjectTodo)
            .where(*filters)
            .order_by(ProjectTodo.updated_at.desc(), ProjectTodo.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return ProjectTodoSearchOut(
        query=normalized_query,
        results=[_search_result(todo, normalized_query) for todo in todos],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(todos) < total,
    )


def _search_result(todo: ProjectTodo, query: str) -> ProjectTodoSearchResultOut:
    return ProjectTodoSearchResultOut(
        id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        title=todo.title,
        description=todo.description,
        status=todo.status.value,
        assigned_window_id=todo.assigned_window_id,
        assigned_agent=todo.assigned_agent,
        updated_at=todo.updated_at,
        matches=[
            *_search_text_matches(todo.title, query, field="title"),
            *_search_text_matches(todo.description or "", query, field="description"),
            *_search_text_matches(todo.project_path, query, field="project_path"),
            *_search_text_matches(todo.status.value, query, field="status"),
            *_search_text_matches(todo.assigned_agent or "", query, field="assigned_agent"),
        ],
    )


def _search_text_matches(
    text: str,
    query: str,
    *,
    field: str,
) -> list[ProjectTodoSearchMatchOut]:
    lowered_text = text.lower()
    lowered_query = query.lower()
    matches: list[ProjectTodoSearchMatchOut] = []
    start = 0
    while len(matches) < 20:
        index = lowered_text.find(lowered_query, start)
        if index < 0:
            break
        matches.append(ProjectTodoSearchMatchOut(field=field, start=index, end=index + len(query)))
        start = index + max(len(query), 1)
    return matches


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
