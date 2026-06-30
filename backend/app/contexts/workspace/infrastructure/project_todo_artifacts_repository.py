from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.contexts.workspace.application.project_todo_artifacts import (
    PROJECT_TODO_ARTIFACT_PURPOSE,
    ProjectTodoArtifactKindRef,
    normalize_project_todo_artifact_kinds,
)
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus


async def list_project_todo_artifacts(
    session: AsyncSession,
    todo_ids: list[UUID],
) -> dict[UUID, list[tuple[ProjectTodoArtifact, TerminalArtifact]]]:
    if not todo_ids:
        return {}
    rows = list(
        await session.execute(
            select(ProjectTodoArtifact, TerminalArtifact)
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
            .where(ProjectTodoArtifact.project_todo_id.in_(todo_ids))
            .order_by(ProjectTodoArtifact.created_at, ProjectTodoArtifact.id)
        )
    )
    grouped: dict[UUID, list[tuple[ProjectTodoArtifact, TerminalArtifact]]] = {}
    for link, artifact in rows:
        grouped.setdefault(link.project_todo_id, []).append((link, artifact))
    return grouped


async def complete_project_todos_after_artifact_status_change(
    session: AsyncSession,
    artifact_id: UUID,
) -> list[ProjectTodo]:
    rows = list(
        await session.execute(
            select(ProjectTodo)
            .join(ProjectTodoArtifact, ProjectTodoArtifact.project_todo_id == ProjectTodo.id)
            .where(
                ProjectTodoArtifact.terminal_artifact_id == artifact_id,
                ProjectTodoArtifact.purpose == PROJECT_TODO_ARTIFACT_PURPOSE,
                ProjectTodo.status == ProjectTodoStatus.dispatched,
            )
        )
    )
    completed: list[ProjectTodo] = []
    for (todo,) in rows:
        if await project_todo_has_incomplete_requested_artifacts(session, todo):
            continue
        from app.contexts.workspace.infrastructure import project_todos_repository

        completed_at = datetime.now(UTC)
        await project_todos_repository._mark_implementation_awaiting_review(session, todo, completed_at)
        completed.append(todo)
    if completed:
        await session.flush()
    return completed


async def project_todo_has_incomplete_requested_artifacts(
    session: AsyncSession,
    todo: ProjectTodo,
) -> bool:
    if not todo.artifact_kinds_json:
        return False
    existing_kinds = await _linked_requested_artifact_statuses(session, todo.id)
    for encoded_kind in normalize_project_todo_artifact_kinds(todo.artifact_kinds_json):
        state = existing_kinds.get(encoded_kind)
        if state is None:
            return True
        status, last_error = state
        if status in {TerminalArtifactStatus.pending, TerminalArtifactStatus.running}:
            return True
        if status is TerminalArtifactStatus.failed and _remote_client_unavailable_error(last_error):
            return True
    return False


async def _linked_requested_artifact_statuses(
    session: AsyncSession,
    todo_id: UUID,
) -> dict[str, tuple[TerminalArtifactStatus, str | None]]:
    rows = await session.execute(
        select(
            TerminalArtifact.artifact_scope,
            TerminalArtifact.artifact_kind,
            TerminalArtifact.status,
            TerminalArtifact.last_error,
        )
        .join(ProjectTodoArtifact, ProjectTodoArtifact.terminal_artifact_id == TerminalArtifact.id)
        .where(
            ProjectTodoArtifact.project_todo_id == todo_id,
            ProjectTodoArtifact.purpose == PROJECT_TODO_ARTIFACT_PURPOSE,
        )
        .order_by(ProjectTodoArtifact.created_at, ProjectTodoArtifact.id)
    )
    statuses: dict[str, tuple[TerminalArtifactStatus, str | None]] = {}
    for scope, kind, status, last_error in rows:
        statuses[ProjectTodoArtifactKindRef(scope=scope or "terminal", kind=kind).encoded] = (
            status,
            last_error,
        )
    return statuses


def _remote_client_unavailable_error(last_error: str | None) -> bool:
    return (last_error or "").lower().startswith("remote client unavailable:")
