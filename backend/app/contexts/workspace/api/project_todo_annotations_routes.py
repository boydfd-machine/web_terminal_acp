from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_todo_annotation_schemas import ProjectTodoAnnotationIn
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_responses import project_todo_response
from app.contexts.workspace.api.schemas import ProjectTodoOut
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_todo_annotations import append_project_todo_annotation
from app.contexts.workspace.application.project_todo_repository import get_project_todo
from app.db import get_session
from app.models import Client, ProjectTodo

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])


@router.post("/{todo_id}/annotations", response_model=ProjectTodoOut)
async def append_todo_annotation(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoAnnotationIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    todo = await _require_todo(session, client_id, normalized_path, todo_id)
    try:
        append_project_todo_annotation(todo, payload.annotation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    assigned_window_id = todo.assigned_window_id
    await session.commit()
    await session.refresh(todo)
    await publish_project_todo_invalidation(
        request,
        client_id,
        window_id=assigned_window_id,
        reason="project_todo_annotation_appended",
    )
    return await project_todo_response(session, client_id, todo)


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


async def _require_todo(session: AsyncSession, client_id: UUID, project_path: str, todo_id: UUID) -> ProjectTodo:
    todo = await get_project_todo(session, client_id, project_path, todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    return todo


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
