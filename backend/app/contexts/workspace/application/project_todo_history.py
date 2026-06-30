from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import McpTokenClaims
from app.models import ProjectTodo, ProjectTodoAuditLog, ProjectTodoVersion
from app.platform.auth_context import current_auth_identity

TITLE_DESCRIPTION_FIELDS = {"title", "description"}
SNAPSHOT_FIELDS = (
    "title",
    "description",
    "parent_todo_id",
    "todo_type_id",
    "status",
    "sort_order",
    "assigned_agent",
    "agent_profile_id",
    "review_strategy",
    "review_status",
    "review_agent",
    "review_agent_profile_id",
    "needs_human_review",
    "review_unseen",
    "review_notes",
    "artifact_kinds",
    "input_artifact_ids",
    "artifact_model_selection",
    "execution_kind",
    "terminal_policy",
    "trigger_strategy",
    "cron_expression",
    "schedule_enabled",
)


@dataclass(frozen=True)
class ProjectTodoHistoryActor:
    actor_type: str
    actor_id: str | None
    actor_display: str | None
    source_window_id: UUID | None = None


def snapshot(todo: ProjectTodo) -> dict[str, Any]:
    return {
        "title": todo.title,
        "description": todo.description,
        "parent_todo_id": todo.parent_todo_id,
        "todo_type_id": todo.todo_type_id,
        "status": todo.status.value,
        "sort_order": todo.sort_order,
        "assigned_agent": todo.assigned_agent,
        "agent_profile_id": todo.agent_profile_id,
        "review_strategy": todo.review_strategy,
        "review_status": todo.review_status,
        "review_agent": todo.review_agent,
        "review_agent_profile_id": todo.review_agent_profile_id,
        "needs_human_review": todo.needs_human_review,
        "review_unseen": todo.review_unseen,
        "review_notes": todo.review_notes,
        "artifact_kinds": deepcopy(todo.artifact_kinds_json or []),
        "input_artifact_ids": deepcopy(todo.input_artifact_ids_json or []),
        "artifact_model_selection": deepcopy(todo.artifact_model_selection_json),
        "execution_kind": todo.execution_kind,
        "terminal_policy": todo.terminal_policy,
        "trigger_strategy": todo.trigger_strategy,
        "cron_expression": todo.cron_expression,
        "schedule_enabled": todo.schedule_enabled,
    }


def user_actor() -> ProjectTodoHistoryActor:
    identity = current_auth_identity()
    if identity is None:
        return ProjectTodoHistoryActor("user", "local", "Local user")
    display = identity.display_name or identity.username or identity.email or identity.user_id
    return ProjectTodoHistoryActor("user", identity.user_id, display)


def agent_actor(source: McpTokenClaims) -> ProjectTodoHistoryActor:
    source_window_id = source.source_window_id
    return ProjectTodoHistoryActor(
        "agent",
        str(source_window_id),
        f"Agent window {str(source_window_id)[:8]}",
        source_window_id,
    )


async def record_created(
    session: AsyncSession,
    todo: ProjectTodo,
    actor: ProjectTodoHistoryActor | None = None,
) -> None:
    actor = actor or user_actor()
    version = _version(
        todo,
        actor,
        version_number=1,
        title=todo.title,
        description=todo.description,
    )
    session.add(version)
    session.add(
        _audit_log(
            todo,
            actor,
            action="created",
            fields=sorted(TITLE_DESCRIPTION_FIELDS),
            to_version_number=1,
        )
    )
    await session.flush()


async def record_update(
    session: AsyncSession,
    todo: ProjectTodo,
    before: dict[str, Any],
    actor: ProjectTodoHistoryActor | None = None,
    requested_fields: set[str] | None = None,
) -> None:
    actor = actor or user_actor()
    after = snapshot(todo)
    fields = sorted(field for field in SNAPSHOT_FIELDS if before.get(field) != after.get(field))
    if requested_fields is not None:
        fields = [field for field in fields if field in requested_fields]
    if not fields:
        return

    from_version_number: int | None = None
    to_version_number: int | None = None
    if TITLE_DESCRIPTION_FIELDS.intersection(fields):
        latest = await _latest_version_number(session, todo.id)
        if latest is None:
            session.add(
                _version(
                    todo,
                    actor,
                    version_number=1,
                    title=before["title"],
                    description=before["description"],
                )
            )
            latest = 1
        from_version_number = latest
        to_version_number = latest + 1
        session.add(
            _version(
                todo,
                actor,
                version_number=to_version_number,
                title=todo.title,
                description=todo.description,
            )
        )

    session.add(
        _audit_log(
            todo,
            actor,
            action="updated",
            fields=fields,
            from_version_number=from_version_number,
            to_version_number=to_version_number,
        )
    )
    await session.flush()


async def list_history(
    session: AsyncSession,
    todo_id: UUID,
) -> tuple[list[ProjectTodoVersion], list[ProjectTodoAuditLog]]:
    versions = list(
        await session.scalars(
            select(ProjectTodoVersion)
            .where(ProjectTodoVersion.project_todo_id == todo_id)
            .order_by(desc(ProjectTodoVersion.version_number))
        )
    )
    audit_logs = list(
        await session.scalars(
            select(ProjectTodoAuditLog)
            .where(ProjectTodoAuditLog.project_todo_id == todo_id)
            .order_by(desc(ProjectTodoAuditLog.created_at), desc(ProjectTodoAuditLog.id))
        )
    )
    return versions, audit_logs


async def restore_version(
    session: AsyncSession,
    todo: ProjectTodo,
    version_number: int,
    actor: ProjectTodoHistoryActor | None = None,
) -> ProjectTodo:
    actor = actor or user_actor()
    target = await session.scalar(
        select(ProjectTodoVersion).where(
            ProjectTodoVersion.project_todo_id == todo.id,
            ProjectTodoVersion.version_number == version_number,
        )
    )
    if target is None:
        raise ValueError("todo version not found")

    before = snapshot(todo)
    todo.title = target.title
    todo.description = target.description
    after = snapshot(todo)
    fields = sorted(
        field for field in TITLE_DESCRIPTION_FIELDS if before.get(field) != after.get(field)
    )
    latest = await _latest_version_number(session, todo.id)
    from_version_number = latest
    to_version_number = latest
    if fields:
        to_version_number = (latest or 0) + 1
        session.add(
            _version(
                todo,
                actor,
                version_number=to_version_number,
                title=todo.title,
                description=todo.description,
            )
        )
    session.add(
        _audit_log(
            todo,
            actor,
            action="restored",
            fields=fields,
            from_version_number=from_version_number,
            to_version_number=to_version_number,
            restored_version_number=target.version_number,
        )
    )
    await session.flush()
    return todo


async def _latest_version_number(session: AsyncSession, todo_id: UUID) -> int | None:
    return await session.scalar(
        select(func.max(ProjectTodoVersion.version_number)).where(
            ProjectTodoVersion.project_todo_id == todo_id
        )
    )


def _version(
    todo: ProjectTodo,
    actor: ProjectTodoHistoryActor,
    *,
    version_number: int,
    title: str,
    description: str | None,
) -> ProjectTodoVersion:
    return ProjectTodoVersion(
        project_todo_id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        version_number=version_number,
        title=title,
        description=description,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        actor_display=actor.actor_display,
        source_window_id=actor.source_window_id,
        created_at=datetime.now(UTC),
    )


def _audit_log(
    todo: ProjectTodo,
    actor: ProjectTodoHistoryActor,
    *,
    action: str,
    fields: list[str],
    from_version_number: int | None = None,
    to_version_number: int | None = None,
    restored_version_number: int | None = None,
) -> ProjectTodoAuditLog:
    return ProjectTodoAuditLog(
        project_todo_id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        action=action,
        fields_json=fields,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        actor_display=actor.actor_display,
        source_window_id=actor.source_window_id,
        from_version_number=from_version_number,
        to_version_number=to_version_number,
        restored_version_number=restored_version_number,
        created_at=datetime.now(UTC),
    )
