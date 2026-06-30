from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import ProjectTodo, ProjectTodoAttachment

ATTACHMENT_STATUS_PENDING = "pending"
ATTACHMENT_STATUS_UPLOADED = "uploaded"
_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$")


async def create_project_todo_attachment(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    filename: str,
    content_type: str,
    size_bytes: int | None,
    settings: Settings | None = None,
) -> ProjectTodoAttachment:
    resolved_settings = settings or get_settings()
    normalized_content_type = validate_attachment_content_type(content_type)
    if size_bytes is not None and size_bytes > resolved_settings.project_todo_attachment_max_bytes:
        raise ValueError("attachment is too large")
    attachment_id = uuid4()
    attachment = ProjectTodoAttachment(
        id=attachment_id,
        project_todo_id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        object_key=object_key_for_attachment(todo, attachment_id, filename),
        filename=safe_attachment_filename(filename),
        content_type=normalized_content_type,
        size_bytes=size_bytes,
        status=ATTACHMENT_STATUS_PENDING,
    )
    session.add(attachment)
    await session.flush()
    return attachment


async def get_project_todo_attachment(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_path: str,
    todo_id: UUID,
    attachment_id: UUID,
) -> ProjectTodoAttachment | None:
    return await session.scalar(
        select(ProjectTodoAttachment).where(
            ProjectTodoAttachment.id == attachment_id,
            ProjectTodoAttachment.project_todo_id == todo_id,
            ProjectTodoAttachment.client_id == client_id,
            ProjectTodoAttachment.project_path == project_path,
        )
    )


async def list_project_todo_attachments_for_todos(
    session: AsyncSession,
    todo_ids: list[UUID],
) -> dict[UUID, list[ProjectTodoAttachment]]:
    if not todo_ids:
        return {}
    rows = list(
        await session.scalars(
            select(ProjectTodoAttachment)
            .where(ProjectTodoAttachment.project_todo_id.in_(todo_ids))
            .order_by(ProjectTodoAttachment.created_at, ProjectTodoAttachment.id)
        )
    )
    grouped: dict[UUID, list[ProjectTodoAttachment]] = {}
    for attachment in rows:
        grouped.setdefault(attachment.project_todo_id, []).append(attachment)
    return grouped


async def mark_project_todo_attachment_uploaded(
    session: AsyncSession,
    attachment: ProjectTodoAttachment,
    *,
    content_type: str | None,
    size_bytes: int | None,
    settings: Settings | None = None,
) -> ProjectTodoAttachment:
    resolved_settings = settings or get_settings()
    if content_type is not None:
        attachment.content_type = validate_attachment_content_type(content_type)
    if size_bytes is not None:
        if size_bytes > resolved_settings.project_todo_attachment_max_bytes:
            raise ValueError("attachment is too large")
        attachment.size_bytes = size_bytes
    attachment.status = ATTACHMENT_STATUS_UPLOADED
    attachment.uploaded_at = datetime.now(UTC)
    await session.flush()
    return attachment


async def delete_project_todo_attachment(
    session: AsyncSession,
    attachment: ProjectTodoAttachment,
) -> None:
    await session.delete(attachment)
    await session.flush()


def object_key_for_attachment(todo: ProjectTodo, attachment_id: UUID, filename: str) -> str:
    return "/".join(
        [
            "project-todos",
            str(todo.client_id),
            str(todo.id),
            str(attachment_id),
            safe_attachment_filename(filename),
        ]
    )


def safe_attachment_filename(filename: str) -> str:
    name = filename.strip().replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    name = _SAFE_FILENAME_CHARS.sub("-", name).strip(".-")
    return name[:255] or "attachment"


def validate_attachment_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower().split(";", maxsplit=1)[0].strip()
    if _MEDIA_TYPE.fullmatch(normalized) is None:
        raise ValueError("attachment must have a valid content type")
    return normalized
