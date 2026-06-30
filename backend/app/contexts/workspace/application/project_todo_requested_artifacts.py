from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models import ProjectTodoArtifact, TerminalArtifact, TerminalArtifactStatus

PROJECT_ARTIFACT_PREFIX = "project:"
LinkedRequestedArtifacts = tuple[set[str], dict[str, TerminalArtifact]]


async def linked_requested_artifacts_for_todos(
    session: AsyncSession,
    todo_ids: list[UUID],
    *,
    purpose: str,
) -> dict[UUID, LinkedRequestedArtifacts]:
    unique_todo_ids = list(dict.fromkeys(todo_ids))
    if not unique_todo_ids:
        return {}

    rows = await session.execute(
        select(ProjectTodoArtifact.project_todo_id, TerminalArtifact)
        .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
        .options(
            load_only(
                TerminalArtifact.id,
                TerminalArtifact.client_id,
                TerminalArtifact.virtual_window_id,
                TerminalArtifact.source_window_id,
                TerminalArtifact.ephemeral_window_id,
                TerminalArtifact.artifact_scope,
                TerminalArtifact.project_path,
                TerminalArtifact.artifact_kind,
                TerminalArtifact.title,
                TerminalArtifact.status,
                TerminalArtifact.metadata_json,
                TerminalArtifact.last_error,
                TerminalArtifact.started_at,
                TerminalArtifact.completed_at,
                TerminalArtifact.created_at,
                TerminalArtifact.updated_at,
            )
        )
        .where(
            ProjectTodoArtifact.project_todo_id.in_(unique_todo_ids),
            ProjectTodoArtifact.purpose == purpose,
        )
        .order_by(ProjectTodoArtifact.project_todo_id, desc(ProjectTodoArtifact.created_at), desc(ProjectTodoArtifact.id))
    )
    linked_by_todo: dict[UUID, LinkedRequestedArtifacts] = {}
    for todo_id, artifact in rows:
        blocking, retryable = linked_by_todo.setdefault(todo_id, (set(), {}))
        encoded_kind = _encoded_artifact_kind(artifact.artifact_scope, artifact.artifact_kind)
        if _linked_artifact_blocks_requested_generation(artifact.status, artifact.last_error):
            blocking.add(encoded_kind)
            retryable.pop(encoded_kind, None)
        elif encoded_kind not in blocking:
            retryable.setdefault(encoded_kind, artifact)
    return linked_by_todo


def _encoded_artifact_kind(scope: str | None, kind: str) -> str:
    return f"{PROJECT_ARTIFACT_PREFIX}{kind}" if (scope or "terminal") == "project" else kind


def _linked_artifact_blocks_requested_generation(
    artifact_status: TerminalArtifactStatus,
    last_error: str | None,
) -> bool:
    return (
        artifact_status is not TerminalArtifactStatus.failed
        or not _remote_client_unavailable_error(last_error)
    )


def _remote_client_unavailable_error(last_error: str | None) -> bool:
    return (last_error or "").lower().startswith("remote client unavailable:")
