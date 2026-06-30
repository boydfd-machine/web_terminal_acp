from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.contexts.workspace.infrastructure.project_todo_attachments_repository import (
    ATTACHMENT_STATUS_UPLOADED,
    create_project_todo_attachment,
    delete_project_todo_attachment,
    get_project_todo_attachment,
    list_project_todo_attachments_for_todos,
    mark_project_todo_attachment_uploaded,
)
from app.contexts.workspace.infrastructure.project_todo_object_storage import (
    PresignedObjectUrl,
    ProjectTodoObjectStorage,
)
from app.models import ProjectTodo, ProjectTodoAttachment


@dataclass(frozen=True)
class ProjectTodoAttachmentUpload:
    attachment: ProjectTodoAttachment
    presigned: PresignedObjectUrl


@dataclass(frozen=True)
class ProjectTodoAttachmentDownload:
    attachment: ProjectTodoAttachment
    presigned: PresignedObjectUrl


async def create_project_todo_attachment_upload(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    filename: str,
    content_type: str,
    size_bytes: int | None,
    storage: ProjectTodoObjectStorage | None = None,
    settings: Settings | None = None,
) -> ProjectTodoAttachmentUpload:
    resolved_settings = settings or get_settings()
    attachment = await create_project_todo_attachment(
        session,
        todo,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        settings=resolved_settings,
    )
    presigned = (storage or ProjectTodoObjectStorage(resolved_settings)).presign_upload(
        attachment.object_key,
        content_type=attachment.content_type,
    )
    return ProjectTodoAttachmentUpload(attachment=attachment, presigned=presigned)


async def complete_project_todo_attachment_upload(
    session: AsyncSession,
    attachment: ProjectTodoAttachment,
    *,
    storage: ProjectTodoObjectStorage | None = None,
    settings: Settings | None = None,
) -> ProjectTodoAttachment:
    resolved_settings = settings or get_settings()
    headers = await (storage or ProjectTodoObjectStorage(resolved_settings)).object_head(attachment.object_key)
    return await mark_project_todo_attachment_uploaded(
        session,
        attachment,
        content_type=headers.get("content-type") or attachment.content_type,
        size_bytes=_content_length(headers.get("content-length")),
        settings=resolved_settings,
    )


async def project_todo_attachment_download(
    attachment: ProjectTodoAttachment,
    *,
    storage: ProjectTodoObjectStorage | None = None,
) -> ProjectTodoAttachmentDownload:
    if attachment.status != ATTACHMENT_STATUS_UPLOADED:
        raise ValueError("attachment is not uploaded")
    presigned = (storage or ProjectTodoObjectStorage()).presign_download(attachment.object_key)
    return ProjectTodoAttachmentDownload(attachment=attachment, presigned=presigned)


async def remove_project_todo_attachment(
    session: AsyncSession,
    attachment: ProjectTodoAttachment,
    *,
    storage: ProjectTodoObjectStorage | None = None,
) -> None:
    await (storage or ProjectTodoObjectStorage()).delete_object(attachment.object_key)
    await delete_project_todo_attachment(session, attachment)


def uploaded_project_todo_attachments(attachments: list[ProjectTodoAttachment]) -> list[ProjectTodoAttachment]:
    return [attachment for attachment in attachments if attachment.status == ATTACHMENT_STATUS_UPLOADED]


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


__all__ = [
    "ATTACHMENT_STATUS_UPLOADED",
    "ProjectTodoAttachmentDownload",
    "ProjectTodoAttachmentUpload",
    "complete_project_todo_attachment_upload",
    "create_project_todo_attachment_upload",
    "get_project_todo_attachment",
    "list_project_todo_attachments_for_todos",
    "project_todo_attachment_download",
    "remove_project_todo_attachment",
    "uploaded_project_todo_attachments",
]
