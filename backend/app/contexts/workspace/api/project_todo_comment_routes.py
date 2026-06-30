from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_responses import project_todo_response
from app.contexts.workspace.api.project_todo_route_helpers import (
    delete_todo_for_route,
    normalize_project_path,
    require_client,
    require_todo,
)
from app.contexts.workspace.api.project_todo_runtime import background_session_factory_for
from app.contexts.workspace.api.schemas import ProjectTodoCommentIn, ProjectTodoOut
from app.contexts.workspace.application.project_todo_artifacts import normalize_project_todo_artifact_kinds
from app.contexts.workspace.application.project_todo_comment import submit_project_todo_comment
from app.db import get_session
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter()


@router.post("/{todo_id}/comment", response_model=ProjectTodoOut)
async def comment_todo(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoCommentIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    client = await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    todo = await require_todo(session, client_id, normalized_path, todo_id)
    try:
        artifact_kinds = (
            normalize_project_todo_artifact_kinds(payload.artifact_kinds)
            if "artifact_kinds" in payload.model_fields_set
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        todo = await submit_project_todo_comment(
            session=session,
            client=client,
            todo=todo,
            comment=payload.comment,
            artifact_kinds=artifact_kinds,
            tmux_manager=tmux_manager,
            registry=client_connection_registry_from_state(request.app.state),
            session_factory=background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    await publish_project_todo_invalidation(
        request,
        client_id,
        window_id=todo.assigned_window_id,
        reason="project_todo_comment_submitted",
    )
    return await project_todo_response(session, client_id, todo)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    assigned_window_id = await delete_todo_for_route(session, client_id, normalized_path, todo_id)
    await session.commit()
    await publish_project_todo_invalidation(
        request,
        client_id,
        window_id=assigned_window_id,
        reason="project_todo_deleted",
    )
