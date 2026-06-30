from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.agent_work_status_cache import cached_agent_work_statuses
from app.contexts.windows.application.assigned_terminal_summary import assigned_terminal_summaries
from app.contexts.workspace.api.project_todo_projection import project_todo_list_item_out, project_todo_out
from app.contexts.workspace.api.schemas import ProjectTodoListItemOut, ProjectTodoOut
from app.contexts.workspace.application.project_todo_dependencies import dependency_graph_for_todos, queued_project_todo_ids
from app.contexts.workspace.application.project_todo_attachments import list_project_todo_attachments_for_todos
from app.contexts.workspace.application.project_todo_repository import (
    child_project_todos_for_todos,
    list_project_todo_artifacts,
    parent_project_todos_for_todos,
    referenced_project_todos_for_todos,
)
from app.contexts.workspace.application.project_todo_runs import (
    recent_project_todo_runs_for_todos,
)
from app.contexts.workspace.application.project_todo_types import todo_type_map_for_todos
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoRun, TerminalArtifact


async def project_todo_response(
    session: AsyncSession,
    client_id: UUID,
    todo: ProjectTodo,
) -> ProjectTodoOut:
    todos = await project_todo_responses(session, client_id, [todo])
    return todos[0]


async def project_todo_responses(
    session: AsyncSession,
    client_id: UUID,
    todos: list[ProjectTodo],
) -> list[ProjectTodoOut]:
    todo_ids = [todo.id for todo in todos]
    artifacts = await list_project_todo_artifacts(session, todo_ids)
    attachments = await list_project_todo_attachments_for_todos(session, todo_ids)
    graph = await dependency_graph_for_todos(session, todo_ids)
    references = await referenced_project_todos_for_todos(session, todos)
    parent_todos = await parent_project_todos_for_todos(session, todos)
    child_todos = await child_project_todos_for_todos(session, todos)
    runs_by_todo = await recent_project_todo_runs_for_todos(session, todo_ids)
    todo_types = await todo_type_map_for_todos(session, todos)
    terminals = await assigned_terminal_summaries(
        session,
        client_id,
        _terminal_window_ids(todos, runs_by_todo, artifacts),
    )
    return [
        project_todo_out(
            todo,
            todo_types[todo.id],
            artifacts.get(todo.id, []),
            attachments.get(todo.id, []),
            graph,
            references.get(todo.id, []),
            parent_todos.get(todo.parent_todo_id) if todo.parent_todo_id is not None else None,
            child_todos.get(todo.id, []),
            terminals.get(todo.assigned_window_id),
            runs_by_todo.get(todo.id, []),
            terminals,
            terminals,
        )
        for todo in todos
    ]


async def project_todo_list_responses(
    session: AsyncSession,
    client_id: UUID,
    todos: list[ProjectTodo],
) -> list[ProjectTodoListItemOut]:
    todo_ids = [todo.id for todo in todos]
    artifacts = await list_project_todo_artifacts(session, todo_ids)
    attachments = await list_project_todo_attachments_for_todos(session, todo_ids)
    todo_types = await todo_type_map_for_todos(session, todos)
    queued_ids = await queued_project_todo_ids(session, todo_ids)
    parent_todos = await parent_project_todos_for_todos(session, todos)
    child_todos = await child_project_todos_for_todos(session, todos)
    references = await referenced_project_todos_for_todos(session, todos)
    runs_by_todo = await recent_project_todo_runs_for_todos(session, todo_ids) if _has_execution_runs(todos) else {}
    terminal_window_ids = _terminal_window_ids(todos, runs_by_todo, artifacts)
    work_statuses = await cached_agent_work_statuses(session, client_id, terminal_window_ids)
    terminals = await assigned_terminal_summaries(
        session,
        client_id,
        terminal_window_ids,
        include_activity=False,
        work_statuses=work_statuses,
    )
    return [
        project_todo_list_item_out(
            todo,
            todo_types[todo.id],
            artifacts.get(todo.id, []),
            attachments.get(todo.id, []),
            parent_todo=parent_todos.get(todo.parent_todo_id) if todo.parent_todo_id is not None else None,
            child_todos=child_todos.get(todo.id, []),
            referenced_todos=references.get(todo.id, []),
            assigned_terminal=terminals.get(todo.assigned_window_id),
            execution_runs=runs_by_todo.get(todo.id, []),
            run_terminals=terminals,
            artifact_terminals=terminals,
            queued_dispatch=todo.id in queued_ids,
        )
        for todo in todos
    ]


def _terminal_window_ids(
    todos: list[ProjectTodo],
    runs_by_todo: dict[UUID, list[ProjectTodoRun]],
    artifacts_by_todo: dict[UUID, list[tuple[ProjectTodoArtifact, TerminalArtifact]]],
) -> list[UUID]:
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for todo in todos:
        if todo.assigned_window_id is not None:
            _append_unique(ordered, seen, todo.assigned_window_id)
        for run in runs_by_todo.get(todo.id, []):
            if run.window_id is not None:
                _append_unique(ordered, seen, run.window_id)
        for _link, artifact in artifacts_by_todo.get(todo.id, []):
            if artifact.ephemeral_window_id is not None:
                _append_unique(ordered, seen, artifact.ephemeral_window_id)
    return ordered


def _has_execution_runs(todos: list[ProjectTodo]) -> bool:
    return any(todo.execution_run_count > 0 for todo in todos)


def _append_unique(ordered: list[UUID], seen: set[UUID], window_id: UUID) -> None:
    if window_id in seen:
        return
    seen.add(window_id)
    ordered.append(window_id)
