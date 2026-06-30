from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import McpTokenClaims
from app.contexts.mcp_acp.api.routes import _require_source_ops
from app.contexts.mcp_acp.application.errors import McpAcpServiceError
from app.contexts.mcp_acp.application.source_client_scope import require_source_scope
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager
from app.contexts.workspace.api import project_todos_routes
from app.contexts.workspace.api.schemas import (
    ProjectTodoCreateIn,
    ProjectTodoDispatchIn,
    ProjectTodoOut,
    ProjectTodoPatchIn,
)
from app.contexts.workspace.application import project_todo_history
from app.db import get_session

router = APIRouter(prefix="/api/agent-ops/project-todos", tags=["agent-ops"])
ProjectPathQuery = Annotated[str, Query(min_length=1, max_length=4096)]
TargetClientIdQuery = Annotated[UUID | None, Query(alias="target_client_id")]


async def _project_todo_client_id(
    session: AsyncSession,
    source: McpTokenClaims,
    target_client_id: UUID | None,
) -> UUID:
    client_id = target_client_id or source.source_client_id
    try:
        scope = await require_source_scope(session, source.source_client_id, source.source_window_id)
        await scope.require_client(session, client_id)
    except McpAcpServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return client_id


@router.post("", response_model=ProjectTodoOut)
async def agent_ops_create_project_todo(
    request: Request,
    payload: ProjectTodoCreateIn,
    project_path: ProjectPathQuery,
    target_client_id: TargetClientIdQuery = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    client_id = await _project_todo_client_id(session, source, target_client_id)
    return await project_todos_routes.create_todo(
        client_id,
        project_path,
        payload,
        request,
        session,
        history_actor=project_todo_history.agent_actor(source),
    )


@router.patch("/{todo_id}", response_model=ProjectTodoOut)
async def agent_ops_patch_project_todo(
    todo_id: UUID,
    request: Request,
    payload: ProjectTodoPatchIn,
    project_path: ProjectPathQuery,
    target_client_id: TargetClientIdQuery = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    client_id = await _project_todo_client_id(session, source, target_client_id)
    return await project_todos_routes.patch_todo(
        client_id,
        todo_id,
        project_path,
        payload,
        request,
        session,
        tmux_manager,
        history_actor=project_todo_history.agent_actor(source),
    )


@router.post("/{todo_id}/dispatch", response_model=ProjectTodoOut)
async def agent_ops_dispatch_project_todo(
    todo_id: UUID,
    request: Request,
    payload: ProjectTodoDispatchIn,
    project_path: ProjectPathQuery,
    target_client_id: TargetClientIdQuery = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    client_id = await _project_todo_client_id(session, source, target_client_id)
    return await project_todos_routes.dispatch_todo(
        client_id,
        todo_id,
        project_path,
        payload,
        request,
        session,
        tmux_manager,
    )
