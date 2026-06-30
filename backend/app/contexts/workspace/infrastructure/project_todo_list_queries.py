from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models import ProjectTodo, ProjectTodoStatus


def project_todos_for_project_statement(
    client_id: UUID,
    project_path: str,
    *,
    updated_at_start: datetime | None = None,
    updated_at_end: datetime | None = None,
):
    filters = [
        ProjectTodo.client_id == client_id,
        ProjectTodo.project_path == project_path,
    ]
    if updated_at_start is not None:
        filters.append(ProjectTodo.updated_at >= updated_at_start)
    if updated_at_end is not None:
        filters.append(ProjectTodo.updated_at < updated_at_end)
    return (
        select(ProjectTodo)
        .options(
            load_only(
                ProjectTodo.id,
                ProjectTodo.client_id,
                ProjectTodo.project_path,
                ProjectTodo.parent_todo_id,
                ProjectTodo.todo_type_id,
                ProjectTodo.title,
                ProjectTodo.description,
                ProjectTodo.status,
                ProjectTodo.sort_order,
                ProjectTodo.assigned_window_id,
                ProjectTodo.assigned_agent,
                ProjectTodo.agent_profile_id,
                ProjectTodo.dispatch_stage,
                ProjectTodo.dispatch_error,
                ProjectTodo.blocked_reason,
                ProjectTodo.awaiting_review_at,
                ProjectTodo.review_status,
                ProjectTodo.review_unseen,
                ProjectTodo.needs_human_review,
                ProjectTodo.implementation_worktree_json,
                ProjectTodo.execution_kind,
                ProjectTodo.terminal_policy,
                ProjectTodo.trigger_strategy,
                ProjectTodo.cron_expression,
                ProjectTodo.schedule_enabled,
                ProjectTodo.execution_run_count,
                ProjectTodo.artifact_kinds_json,
                ProjectTodo.artifact_model_selection_json,
                ProjectTodo.input_artifact_ids_json,
                ProjectTodo.created_at,
                ProjectTodo.updated_at,
            )
        )
        .where(*filters)
        .order_by(desc(ProjectTodo.sort_order), desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
    )


async def list_project_todos_for_project(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    updated_at_start: datetime | None = None,
    updated_at_end: datetime | None = None,
) -> list[ProjectTodo]:
    return list(
        await session.scalars(
            project_todos_for_project_statement(
                client_id,
                project_path,
                updated_at_start=updated_at_start,
                updated_at_end=updated_at_end,
            )
        )
    )


async def list_project_todo_artifact_candidates(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> list[ProjectTodo]:
    return list(
        await session.scalars(
            select(ProjectTodo)
            .where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.project_path == project_path,
                ProjectTodo.artifact_kinds_json.is_not(None),
                ProjectTodo.assigned_window_id.is_not(None),
                ProjectTodo.status.in_((ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done)),
            )
            .order_by(desc(ProjectTodo.sort_order), desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
        )
    )
