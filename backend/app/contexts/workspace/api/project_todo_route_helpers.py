from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_todo_history import ProjectTodoHistoryActor
from app.contexts.workspace.application.project_todo_repository import delete_project_todo, get_project_todo
from app.models import Client, ProjectTodo


def normalized_project_todo_search_query(q: str) -> str:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="search query is required")
    return query


async def require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


async def require_todo(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
) -> ProjectTodo:
    todo = await get_project_todo(session, client_id, project_path, todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    return todo


async def delete_todo_for_route(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
) -> UUID | None:
    todo = await get_project_todo(session, client_id, project_path, todo_id)
    assigned_window_id = todo.assigned_window_id if todo is not None else None
    deleted = await delete_project_todo(session, client_id, project_path, todo_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    return assigned_window_id


def normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def project_todo_history_actor_from_request(request: Request) -> ProjectTodoHistoryActor | None:
    return getattr(request.state, "project_todo_history_actor", None)
