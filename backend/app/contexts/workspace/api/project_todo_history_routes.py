from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.api.project_todo_history_schemas import (
    ProjectTodoAuditLogOut,
    ProjectTodoHistoryOut,
    ProjectTodoVersionOut,
)
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_responses import project_todo_response
from app.contexts.workspace.api.project_todo_route_helpers import (
    normalize_project_path,
    require_client,
    require_todo,
)
from app.contexts.workspace.api.schemas import ProjectTodoOut
from app.contexts.workspace.application import project_todo_history
from app.db import get_session
from app.models import ProjectTodoAuditLog, ProjectTodoVersion

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])


@router.get("/{todo_id}/history", response_model=ProjectTodoHistoryOut)
async def get_todo_history(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoHistoryOut:
    await require_client(session, client_id)
    todo = await require_todo(session, client_id, normalize_project_path(project_path), todo_id)
    versions, audit_logs = await project_todo_history.list_history(session, todo.id)
    return ProjectTodoHistoryOut(
        todo_id=todo.id,
        versions=[_version_out(version) for version in versions],
        audit_logs=[_audit_log_out(log) for log in audit_logs],
    )


@router.post("/{todo_id}/versions/{version_number}/restore", response_model=ProjectTodoOut)
async def restore_todo_version(
    client_id: UUID,
    todo_id: UUID,
    version_number: int,
    project_path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    todo = await require_todo(session, client_id, normalize_project_path(project_path), todo_id)
    try:
        await project_todo_history.restore_version(session, todo, version_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(todo)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_version_restored")
    return await project_todo_response(session, client_id, todo)


def _version_out(version: ProjectTodoVersion) -> ProjectTodoVersionOut:
    return ProjectTodoVersionOut(
        id=version.id,
        todo_id=version.project_todo_id,
        version_number=version.version_number,
        title=version.title,
        description=version.description,
        actor_type=version.actor_type,
        actor_id=version.actor_id,
        actor_display=version.actor_display,
        source_window_id=version.source_window_id,
        created_at=version.created_at,
    )


def _audit_log_out(log: ProjectTodoAuditLog) -> ProjectTodoAuditLogOut:
    return ProjectTodoAuditLogOut(
        id=log.id,
        todo_id=log.project_todo_id,
        action=log.action,
        fields=log.fields_json,
        actor_type=log.actor_type,
        actor_id=log.actor_id,
        actor_display=log.actor_display,
        source_window_id=log.source_window_id,
        from_version_number=log.from_version_number,
        to_version_number=log.to_version_number,
        restored_version_number=log.restored_version_number,
        created_at=log.created_at,
    )
