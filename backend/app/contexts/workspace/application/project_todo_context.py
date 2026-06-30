from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.windows.application.agent_record_projection import (
    CompactAgentChatMessage,
    load_compact_agent_chat_messages,
)
from app.contexts.workspace.application.project_todo_dependencies import dependency_graph_for_todos
from app.contexts.workspace.application.project_todo_repository import (
    list_project_todo_artifacts,
    referenced_project_todos_for_todos,
)
from app.contexts.workspace.application.project_todo_types import get_project_todo_type
from app.contexts.workspace.application.project_todo_reviews import (
    list_project_todo_review_runs,
    list_project_todo_review_targets,
    list_project_todo_work_snapshots,
)
from app.models import (
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoReviewRun,
    ProjectTodoReviewTarget,
    ProjectTodoWorkSnapshot,
    TerminalArtifact,
)


async def project_todo_context_by_id(
    session: AsyncSession,
    todo_id: UUID,
    *,
    client_id: UUID | None = None,
    include_agent_record: bool = True,
    include_worktree: bool = True,
    include_related: bool = True,
    agent_record_message_limit: int = 200,
) -> dict[str, Any] | None:
    todo = await session.get(ProjectTodo, todo_id)
    if todo is None:
        return None
    if client_id is not None and todo.client_id != client_id:
        return None

    context: dict[str, Any] = {"todo": await _todo_payload(session, todo)}
    if include_related:
        context["relationships"] = await _relationships_payload(session, todo)
        context["artifacts"] = await _artifacts_payload(session, todo)
    if include_worktree:
        context["worktree"] = todo.implementation_worktree_json
        context["work_snapshots"] = [
            _snapshot_payload(snapshot)
            for snapshot in await list_project_todo_work_snapshots(session, todo.id)
        ]
        context["review_targets"] = [
            _target_payload(target)
            for target in await list_project_todo_review_targets(session, todo.id)
        ]
        context["review_runs"] = [
            _run_payload(run)
            for run in await list_project_todo_review_runs(session, todo.id)
        ]
    if include_agent_record:
        context["agent_records"] = await _agent_records_payload(
            session,
            todo,
            message_limit=agent_record_message_limit,
        )
    return context


async def _todo_payload(session: AsyncSession, todo: ProjectTodo) -> dict[str, Any]:
    todo_type = await get_project_todo_type(session, todo.client_id, todo.project_path, todo.todo_type_id)
    return {
        "id": str(todo.id),
        "client_id": str(todo.client_id),
        "project_path": todo.project_path,
        "todo_type_id": todo.todo_type_id,
        "todo_type": _todo_type_payload(todo_type),
        "title": todo.title,
        "description": todo.description,
        "status": todo.status.value,
        "assigned_window_id": _uuid(todo.assigned_window_id),
        "assigned_agent": todo.assigned_agent,
        "agent_profile_id": todo.agent_profile_id,
        "dispatch_prompt": todo.dispatch_prompt,
        "dispatch_stage": todo.dispatch_stage,
        "dispatch_error": todo.dispatch_error,
        "dispatched_at": _iso(todo.dispatched_at),
        "awaiting_review_at": _iso(todo.awaiting_review_at),
        "completed_at": _iso(todo.completed_at),
        "review_status": todo.review_status,
        "review_strategy": todo.review_strategy,
        "review_window_id": _uuid(todo.review_window_id),
        "review_prompt": todo.review_prompt,
        "review_dispatched_at": _iso(todo.review_dispatched_at),
        "reviewed_at": _iso(todo.reviewed_at),
        "needs_human_review": todo.needs_human_review,
        "review_notes": todo.review_notes,
        "created_at": _iso(todo.created_at),
        "updated_at": _iso(todo.updated_at),
    }


def _todo_type_payload(todo_type) -> dict[str, Any] | None:
    if todo_type is None:
        return None
    return {
        "id": todo_type.id,
        "scope": todo_type.scope,
        "client_id": _uuid(todo_type.client_id),
        "project_path": todo_type.project_path,
        "name": todo_type.name,
        "description": todo_type.description,
        "agent": todo_type.agent,
        "agent_profile_id": todo_type.agent_profile_id,
    }


async def _relationships_payload(session: AsyncSession, todo: ProjectTodo) -> dict[str, Any]:
    graph = await dependency_graph_for_todos(session, [todo.id])
    referenced = (await referenced_project_todos_for_todos(session, [todo])).get(todo.id, [])
    return {
        "dependencies": [_relation_payload(item) for item in graph.dependencies.get(todo.id, [])],
        "dependents": [_relation_payload(item) for item in graph.dependents.get(todo.id, [])],
        "referenced_todos": [_referenced_todo_payload(item) for item in referenced],
    }


async def _artifacts_payload(session: AsyncSession, todo: ProjectTodo) -> list[dict[str, Any]]:
    artifacts = (await list_project_todo_artifacts(session, [todo.id])).get(todo.id, [])
    return [_artifact_payload(link, artifact) for link, artifact in artifacts]


async def _agent_records_payload(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    message_limit: int,
) -> list[dict[str, Any]]:
    windows = [
        ("implementation", todo.assigned_window_id),
        ("review", todo.review_window_id),
    ]
    records: list[dict[str, Any]] = []
    for role, window_id in windows:
        if window_id is None:
            continue
        messages = await load_compact_agent_chat_messages(
            session,
            client_id=todo.client_id,
            window_id=window_id,
            message_limit=message_limit,
        )
        records.append({
            "role": role,
            "window_id": str(window_id),
            "turns": _turns_payload(messages),
        })
    return records


def _turns_payload(messages: list[CompactAgentChatMessage]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for message in messages:
        if message.role == "user":
            current = {
                "user_input": message.body,
                "user_created_at": _iso(message.created_at),
                "last_agent_output": None,
                "last_agent_created_at": None,
            }
            turns.append(current)
            continue
        if current is None:
            current = {"user_input": None, "user_created_at": None}
            turns.append(current)
        current["last_agent_output"] = message.body
        current["last_agent_created_at"] = _iso(message.created_at)
    return turns


def _relation_payload(item) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "status": item.status.value,
        "completed_at": _iso(item.completed_at),
    }


def _referenced_todo_payload(todo: ProjectTodo) -> dict[str, Any]:
    return {
        "id": str(todo.id),
        "title": todo.title,
        "description": todo.description,
        "status": todo.status.value,
    }


def _artifact_payload(link: ProjectTodoArtifact, artifact: TerminalArtifact) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "artifact_id": str(artifact.id),
        "client_id": str(artifact.client_id),
        "window_id": str(artifact.virtual_window_id),
        "source_window_id": _uuid(artifact.source_window_id),
        "ephemeral_window_id": _uuid(artifact.ephemeral_window_id),
        "review_run_id": _uuid(link.review_run_id),
        "created_by_window_id": _uuid(link.created_by_window_id),
        "artifact_scope": artifact.artifact_scope,
        "project_path": artifact.project_path,
        "title": artifact.title,
        "artifact_kind": artifact.artifact_kind,
        "status": artifact.status.value,
        "purpose": link.purpose,
        "metadata_json": artifact.metadata_json,
        "last_error": artifact.last_error,
        "started_at": _iso(artifact.started_at),
        "completed_at": _iso(artifact.completed_at),
        "created_at": _iso(link.created_at),
        "updated_at": _iso(artifact.updated_at),
    }


def _snapshot_payload(snapshot: ProjectTodoWorkSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "todo_id": str(snapshot.project_todo_id),
        "client_id": str(snapshot.client_id),
        "project_path": snapshot.project_path,
        "window_id": _uuid(snapshot.window_id),
        "role": snapshot.role,
        "branch_name": snapshot.branch_name,
        "base_ref": snapshot.base_ref,
        "base_sha": snapshot.base_sha,
        "head_sha": snapshot.head_sha,
        "commit_shas": snapshot.commit_shas_json or [],
        "diff_stat": snapshot.diff_stat_json,
        "changed_files": snapshot.changed_files_json or [],
        "dirty_state": snapshot.dirty_state,
        "captured_at": _iso(snapshot.captured_at),
    }


def _target_payload(target: ProjectTodoReviewTarget) -> dict[str, Any]:
    return {
        "id": str(target.id),
        "todo_id": str(target.project_todo_id),
        "work_snapshot_id": str(target.work_snapshot_id),
        "provider": target.provider,
        "external_id": target.external_id,
        "url": target.url,
        "status": target.status,
        "base_sha": target.base_sha,
        "head_sha": target.head_sha,
        "created_at": _iso(target.created_at),
        "updated_at": _iso(target.updated_at),
    }


def _run_payload(run: ProjectTodoReviewRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "todo_id": str(run.project_todo_id),
        "review_target_id": str(run.review_target_id),
        "review_window_id": _uuid(run.review_window_id),
        "agent_client": run.agent_client,
        "agent_profile_id": run.agent_profile_id,
        "status": run.status,
        "summary": run.summary,
        "findings": run.findings_json or [],
        "test_commands": run.test_commands_json or [],
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "last_error": run.last_error,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
    }


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
