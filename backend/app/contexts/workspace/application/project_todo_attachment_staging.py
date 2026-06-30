from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from app.config import Settings, get_settings
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.workspace.application.project_todo_attachments import (
    list_project_todo_attachments_for_todos,
    uploaded_project_todo_attachments,
)
from app.contexts.workspace.infrastructure.project_todo_object_storage import ProjectTodoObjectStorage
from app.models import ProjectTodoAttachment


@dataclass(frozen=True)
class StagedProjectTodoAttachment:
    filename: str
    path: str
    content_type: str
    size_bytes: int | None


async def stage_project_todo_attachments_for_prompt(
    *,
    client_id: UUID,
    todo_id: UUID,
    prompt: str,
    session_factory: Callable[[], object],
    broker: TerminalBroker,
    storage: ProjectTodoObjectStorage | None = None,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    async with session_factory() as session:
        grouped = await list_project_todo_attachments_for_todos(session, [todo_id])
    attachments = uploaded_project_todo_attachments(grouped.get(todo_id, []))
    if not attachments:
        return prompt

    object_storage = storage or ProjectTodoObjectStorage(resolved_settings)
    staged: list[StagedProjectTodoAttachment] = []
    for attachment in attachments:
        data = await object_storage.read_object(attachment.object_key)
        if len(data) > resolved_settings.project_todo_attachment_max_bytes:
            raise ValueError(f"attachment is too large: {attachment.filename}")
        target_path = _attachment_target_path(resolved_settings, attachment)
        await broker.write_file_bytes(client_id, target_path, data, overwrite=True)
        staged.append(
            StagedProjectTodoAttachment(
                filename=attachment.filename,
                path=target_path,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes or len(data),
            )
        )
    return append_project_todo_attachment_context(prompt, staged)


def append_project_todo_attachment_context(
    prompt: str,
    attachments: list[StagedProjectTodoAttachment],
) -> str:
    if not attachments:
        return prompt
    lines = ["# Attached Files"]
    for index, attachment in enumerate(attachments, start=1):
        size = f", {attachment.size_bytes} bytes" if attachment.size_bytes is not None else ""
        lines.append(
            f"{index}. {attachment.filename} ({attachment.content_type}{size})\n"
            f"   Local file path: {attachment.path}"
        )
    lines.append("Use these local file paths when an agent-client supports file path input.")
    return f"{prompt.rstrip()}\n\n" + "\n".join(lines)


def _attachment_target_path(settings: Settings, attachment: ProjectTodoAttachment) -> str:
    root = PurePosixPath(settings.project_todo_attachment_client_temp_root)
    return str(root / str(attachment.project_todo_id) / str(attachment.id) / attachment.filename)
