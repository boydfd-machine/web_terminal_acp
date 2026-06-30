from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_todo_type_projection import project_todo_type_out
from app.contexts.workspace.api.schemas import (
    ProjectTodoTypeListOut,
    ProjectTodoTypeOut,
    ProjectTodoTypePatchIn,
    ProjectTodoTypeUpsertIn,
)
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_todo_artifacts import normalize_project_todo_artifact_kinds
from app.contexts.workspace.application.project_todo_input_artifacts import normalize_project_todo_input_artifact_ids
from app.contexts.workspace.application.project_todo_types import (
    DEFAULT_PROJECT_TODO_TYPE_ID,
    delete_system_project_todo_type,
    get_project_todo_type,
    list_project_todo_types,
    patch_system_project_todo_type,
    upsert_system_project_todo_type,
)
from app.db import get_session
from app.models import Client
from app.platform.ui_events import ui_event_hub_from_state
from app.platform.ui_settings_repository import current_user_setting_owner_id

router = APIRouter(prefix="/api/clients/{client_id}/projects/todo-types", tags=["project_todo_types"])

ProjectPathQuery = Query(..., min_length=1, max_length=4096)


@router.get("", response_model=ProjectTodoTypeListOut)
async def list_todo_types(
    client_id: UUID,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoTypeListOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    todo_types = await list_project_todo_types(
        session,
        client_id,
        normalized_path,
        owner_user_id=current_user_setting_owner_id(),
    )
    await session.commit()
    return ProjectTodoTypeListOut(todo_types=[project_todo_type_out(todo_type) for todo_type in todo_types])


@router.get("/{todo_type_id}", response_model=ProjectTodoTypeOut)
async def read_todo_type(
    client_id: UUID,
    todo_type_id: str,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoTypeOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    todo_type = await get_project_todo_type(
        session,
        client_id,
        normalized_path,
        todo_type_id,
        owner_user_id=current_user_setting_owner_id(),
    )
    if todo_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo type not found")
    await session.commit()
    return project_todo_type_out(todo_type)


@router.post("/system", response_model=ProjectTodoTypeOut)
async def upsert_system_todo_type(
    client_id: UUID,
    payload: ProjectTodoTypeUpsertIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoTypeOut:
    await _require_client(session, client_id)
    try:
        artifact_kinds = normalize_project_todo_artifact_kinds(payload.artifact_kinds)
        input_artifact_ids = normalize_project_todo_input_artifact_ids(payload.input_artifact_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if payload.id == DEFAULT_PROJECT_TODO_TYPE_ID:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="default todo type is reserved")
    todo_type = await upsert_system_project_todo_type(
        session,
        todo_type_id=payload.id,
        name=payload.name,
        description=payload.description,
        agent=payload.agent,
        agent_profile_id=payload.agent_profile_id,
        artifact_kinds=artifact_kinds,
        input_artifact_ids=input_artifact_ids,
        dispatch_template=payload.dispatch_template or None,
        owner_user_id=current_user_setting_owner_id(),
    )
    await session.commit()
    await session.refresh(todo_type)
    await _publish_project_todo_type_invalidation(request, client_id, reason="project_todo_type_upserted")
    return project_todo_type_out(todo_type)


@router.patch("/system/{todo_type_id}", response_model=ProjectTodoTypeOut)
async def patch_system_todo_type(
    client_id: UUID,
    todo_type_id: str,
    payload: ProjectTodoTypePatchIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoTypeOut:
    await _require_client(session, client_id)
    artifact_kinds: list[str] | None = None
    if "artifact_kinds" in payload.model_fields_set:
        try:
            artifact_kinds = normalize_project_todo_artifact_kinds(payload.artifact_kinds)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    input_artifact_ids: list[str] | None = None
    if "input_artifact_ids" in payload.model_fields_set:
        try:
            input_artifact_ids = normalize_project_todo_input_artifact_ids(payload.input_artifact_ids)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    todo_type = await patch_system_project_todo_type(
        session,
        todo_type_id,
        name=payload.name,
        description_provided="description" in payload.model_fields_set,
        description=payload.description,
        agent_provided="agent" in payload.model_fields_set,
        agent=payload.agent,
        agent_profile_id_provided="agent_profile_id" in payload.model_fields_set,
        agent_profile_id=payload.agent_profile_id,
        artifact_kinds_provided="artifact_kinds" in payload.model_fields_set,
        artifact_kinds=artifact_kinds,
        input_artifact_ids_provided="input_artifact_ids" in payload.model_fields_set,
        input_artifact_ids=input_artifact_ids,
        dispatch_template_provided="dispatch_template" in payload.model_fields_set,
        dispatch_template=payload.dispatch_template or None,
        owner_user_id=current_user_setting_owner_id(),
    )
    if todo_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo type not found")
    await session.commit()
    await session.refresh(todo_type)
    await _publish_project_todo_type_invalidation(request, client_id, reason="project_todo_type_updated")
    return project_todo_type_out(todo_type)


@router.delete("/system/{todo_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_todo_type(
    client_id: UUID,
    todo_type_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    await _require_client(session, client_id)
    if todo_type_id == DEFAULT_PROJECT_TODO_TYPE_ID:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="default todo type cannot be deleted")
    try:
        deleted = await delete_system_project_todo_type(
            session,
            todo_type_id,
            owner_user_id=current_user_setting_owner_id(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo type not found")
    await session.commit()
    await _publish_project_todo_type_invalidation(request, client_id, reason="project_todo_type_deleted")


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _publish_project_todo_type_invalidation(request: Request, client_id: UUID, *, reason: str) -> None:
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["project_todo_types", "project_todos"],
        client_id=client_id,
        reason=reason,
    )
