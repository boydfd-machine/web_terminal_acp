from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_responses import project_todo_response
from app.contexts.workspace.api.project_todo_route_helpers import (
    normalize_project_path,
    require_client,
    require_todo,
)
from app.contexts.workspace.api.schemas import ProjectTodoArtifactLinkIn, ProjectTodoOut
from app.contexts.workspace.application.project_todo_repository import link_project_todo_artifact
from app.db import get_session

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])


@router.post("/{todo_id}/artifacts", response_model=ProjectTodoOut)
async def link_todo_artifact(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoArtifactLinkIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    todo = await require_todo(session, client_id, normalize_project_path(project_path), todo_id)
    link = await link_project_todo_artifact(session, todo, payload.artifact_id, purpose=payload.purpose)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    await session.commit()
    await session.refresh(todo)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_artifact_linked")
    return await project_todo_response(session, client_id, todo)
