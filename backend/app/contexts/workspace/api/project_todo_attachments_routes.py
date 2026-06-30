from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_todo_attachment_schemas import (
    ProjectTodoAttachmentCreateIn,
    ProjectTodoAttachmentDownloadOut,
    ProjectTodoAttachmentOut,
    ProjectTodoAttachmentUploadOut,
)
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_projection import project_todo_attachment_out
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_todo_attachments import (
    complete_project_todo_attachment_upload,
    create_project_todo_attachment_upload,
    get_project_todo_attachment,
    project_todo_attachment_download,
    remove_project_todo_attachment,
)
from app.contexts.workspace.application.project_todo_repository import get_project_todo
from app.db import get_session
from app.models import ProjectTodo, ProjectTodoAttachment

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])


@router.post("/{todo_id}/attachments", response_model=ProjectTodoAttachmentUploadOut)
async def create_todo_attachment_upload(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoAttachmentCreateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoAttachmentUploadOut:
    await _require_client(session, client_id)
    todo = await _require_todo(session, client_id, _normalize_project_path(project_path), todo_id)
    try:
        upload = await create_project_todo_attachment_upload(
            session,
            todo,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(upload.attachment)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_attachment_created")
    return ProjectTodoAttachmentUploadOut(
        attachment=project_todo_attachment_out(upload.attachment),
        upload_url=upload.presigned.url,
        upload_headers=upload.presigned.headers,
        expires_at=upload.presigned.expires_at,
    )


@router.post("/{todo_id}/attachments/{attachment_id}/complete", response_model=ProjectTodoAttachmentOut)
async def complete_todo_attachment_upload(
    client_id: UUID,
    todo_id: UUID,
    attachment_id: UUID,
    project_path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoAttachmentOut:
    await _require_client(session, client_id)
    attachment = await _require_attachment(session, client_id, _normalize_project_path(project_path), todo_id, attachment_id)
    try:
        await complete_project_todo_attachment_upload(session, attachment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"attachment object is not available: {exc.response.status_code}",
        ) from exc
    await session.commit()
    await session.refresh(attachment)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_attachment_uploaded")
    return project_todo_attachment_out(attachment)


@router.get("/{todo_id}/attachments/{attachment_id}/download", response_model=ProjectTodoAttachmentDownloadOut)
async def download_todo_attachment(
    client_id: UUID,
    todo_id: UUID,
    attachment_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoAttachmentDownloadOut:
    await _require_client(session, client_id)
    attachment = await _require_attachment(session, client_id, _normalize_project_path(project_path), todo_id, attachment_id)
    try:
        download = await project_todo_attachment_download(attachment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProjectTodoAttachmentDownloadOut(
        attachment=project_todo_attachment_out(download.attachment),
        download_url=download.presigned.url,
        expires_at=download.presigned.expires_at,
    )


@router.delete("/{todo_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo_attachment(
    client_id: UUID,
    todo_id: UUID,
    attachment_id: UUID,
    project_path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    await _require_client(session, client_id)
    attachment = await _require_attachment(session, client_id, _normalize_project_path(project_path), todo_id, attachment_id)
    await remove_project_todo_attachment(session, attachment)
    await session.commit()
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_attachment_deleted")


async def _require_client(session: AsyncSession, client_id: UUID) -> None:
    if await get_client(session, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")


async def _require_todo(session: AsyncSession, client_id: UUID, project_path: str, todo_id: UUID) -> ProjectTodo:
    todo = await get_project_todo(session, client_id, project_path, todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    return todo


async def _require_attachment(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
    attachment_id: UUID,
) -> ProjectTodoAttachment:
    attachment = await get_project_todo_attachment(
        session,
        client_id=client_id,
        project_path=project_path,
        todo_id=todo_id,
        attachment_id=attachment_id,
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attachment not found")
    return attachment


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
