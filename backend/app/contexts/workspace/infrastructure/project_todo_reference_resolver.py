from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.domain.project_todo_references import (
    ProjectTodoReferenceRequest,
    project_todo_reference_requests,
)
from app.models import ProjectTodo


async def resolve_project_todo_references_from_text(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_path: str,
    source_todo_id: UUID,
    text: str | None,
) -> list[ProjectTodo]:
    reference_requests = project_todo_reference_requests(text)
    if not reference_requests:
        return []

    resolved = await _resolve_reference_requests(
        session,
        client_id=client_id,
        project_path=project_path,
        requests_by_source={source_todo_id: reference_requests},
    )
    return resolved.get(source_todo_id, [])


async def referenced_project_todos_for_todos(
    session: AsyncSession,
    todos: list[ProjectTodo],
) -> dict[UUID, list[ProjectTodo]]:
    if not todos:
        return {}

    first_todo = todos[0]
    return await _resolve_reference_requests(
        session,
        client_id=first_todo.client_id,
        project_path=first_todo.project_path,
        requests_by_source={
            todo.id: project_todo_reference_requests(todo.description)
            for todo in todos
        },
    )


async def _resolve_reference_requests(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_path: str,
    requests_by_source: dict[UUID, list[ProjectTodoReferenceRequest]],
) -> dict[UUID, list[ProjectTodo]]:
    requested_titles = {
        request.title
        for requests in requests_by_source.values()
        for request in requests
        if request.todo_id is None
    }
    requested_ids = {
        request.todo_id
        for requests in requests_by_source.values()
        for request in requests
        if request.todo_id is not None
    }
    if not requested_titles and not requested_ids:
        return {source_id: [] for source_id in requests_by_source}

    title_rows: list[ProjectTodo] = []
    id_rows: list[ProjectTodo] = []
    project_scope = (
        ProjectTodo.client_id == client_id,
        ProjectTodo.project_path == project_path,
    )
    if requested_titles:
        title_rows = list(
            await session.scalars(
                select(ProjectTodo)
                .where(
                    *project_scope,
                    ProjectTodo.title.in_(requested_titles),
                )
                .order_by(ProjectTodo.sort_order, desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
            )
        )
    if requested_ids:
        id_rows = list(
            await session.scalars(
                select(ProjectTodo)
                .where(
                    *project_scope,
                    ProjectTodo.id.in_(requested_ids),
                )
            )
        )

    candidates_by_id = {candidate.id: candidate for candidate in id_rows}
    candidates_by_title: dict[str, list[ProjectTodo]] = {}
    for candidate in title_rows:
        candidates_by_title.setdefault(candidate.title, []).append(candidate)

    return {
        source_id: _resolve_references_for_source(
            requests,
            source_id=source_id,
            candidates_by_id=candidates_by_id,
            candidates_by_title=candidates_by_title,
        )
        for source_id, requests in requests_by_source.items()
    }


def _resolve_references_for_source(
    requests: list[ProjectTodoReferenceRequest],
    *,
    source_id: UUID,
    candidates_by_id: dict[UUID, ProjectTodo],
    candidates_by_title: dict[str, list[ProjectTodo]],
) -> list[ProjectTodo]:
    references: list[ProjectTodo] = []
    referenced_ids: set[UUID] = set()
    for request in requests:
        if request.todo_id is not None:
            match = candidates_by_id.get(request.todo_id)
            if match is not None and (match.id == source_id or match.id in referenced_ids):
                match = None
        else:
            match = next(
                (
                    candidate
                    for candidate in candidates_by_title.get(request.title, [])
                    if candidate.id != source_id and candidate.id not in referenced_ids
                ),
                None,
            )
        if match is not None:
            references.append(match)
            referenced_ids.add(match.id)
    return references
