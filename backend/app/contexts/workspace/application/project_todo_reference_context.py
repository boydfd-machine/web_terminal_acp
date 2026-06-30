from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.windows.application.agent_record_projection import (
    CompactAgentChatMessage,
    load_compact_agent_chat_messages,
)
from app.contexts.workspace.application.project_todo_prompt_references import (
    ProjectTodoPromptArtifact,
    ProjectTodoPromptReference,
    ProjectTodoPromptSession,
    ProjectTodoPromptTerminal,
    ProjectTodoPromptTurn,
)
from app.contexts.workspace.application.project_todo_repository import list_project_todo_artifacts
from app.models import ProjectTodo, TerminalArtifact, VirtualWindow

PROJECT_TODO_REFERENCE_AGENT_RECORD_MESSAGE_LIMIT = 200


async def prompt_references_for_project_todos(
    session: AsyncSession,
    referenced_todos: list[ProjectTodo],
) -> list[ProjectTodoPromptReference]:
    if not referenced_todos:
        return []

    todo_ids = [todo.id for todo in referenced_todos]
    artifacts_by_todo = await list_project_todo_artifacts(session, todo_ids)
    terminal_titles = await _terminal_titles_by_id(
        session,
        _referenced_terminal_ids(referenced_todos, artifacts_by_todo),
    )
    references: list[ProjectTodoPromptReference] = []
    for todo in referenced_todos:
        references.append(
            ProjectTodoPromptReference(
                title=todo.title,
                todo_id=str(todo.id),
                sessions=await _session_references(session, todo, terminal_titles),
                artifacts=[
                    _artifact_reference(artifact, terminal_titles)
                    for _link, artifact in artifacts_by_todo.get(todo.id, [])
                ],
                terminals=[
                    ProjectTodoPromptTerminal(
                        terminal_id=str(window_id),
                        title=terminal_titles.get(window_id),
                    )
                    for window_id in _todo_terminal_ids(todo, artifacts_by_todo.get(todo.id, []))
                ],
            )
        )
    return references


async def _session_references(
    session: AsyncSession,
    todo: ProjectTodo,
    terminal_titles: dict[UUID, str],
) -> list[ProjectTodoPromptSession]:
    references: list[ProjectTodoPromptSession] = []
    for role, window_id in (("implementation", todo.assigned_window_id), ("review", todo.review_window_id)):
        if window_id is None:
            continue
        messages = await load_compact_agent_chat_messages(
            session,
            client_id=todo.client_id,
            window_id=window_id,
            message_limit=PROJECT_TODO_REFERENCE_AGENT_RECORD_MESSAGE_LIMIT,
        )
        references.append(
            ProjectTodoPromptSession(
                role=role,
                terminal_id=str(window_id),
                terminal_title=terminal_titles.get(window_id),
                turns=_turns(messages),
            )
        )
    return references


def _turns(messages: list[CompactAgentChatMessage]) -> list[ProjectTodoPromptTurn]:
    turns: list[ProjectTodoPromptTurn] = []
    current: ProjectTodoPromptTurn | None = None
    for message in messages:
        if message.role == "user":
            current = ProjectTodoPromptTurn(user_input=message.body)
            turns.append(current)
            continue
        if current is None:
            current = ProjectTodoPromptTurn()
            turns.append(current)
        current_index = len(turns) - 1
        turns[current_index] = ProjectTodoPromptTurn(
            user_input=current.user_input,
            last_agent_output=message.body,
        )
        current = turns[current_index]
    return turns


def _artifact_reference(
    artifact: TerminalArtifact,
    terminal_titles: dict[UUID, str],
) -> ProjectTodoPromptArtifact:
    terminal_id = artifact.ephemeral_window_id or artifact.virtual_window_id or artifact.source_window_id
    return ProjectTodoPromptArtifact(
        artifact_id=str(artifact.id),
        title=artifact.title,
        terminal_id=str(terminal_id) if terminal_id is not None else None,
        terminal_title=terminal_titles.get(terminal_id) if terminal_id is not None else None,
    )


def _referenced_terminal_ids(
    todos: list[ProjectTodo],
    artifacts_by_todo: dict[UUID, list[tuple[object, TerminalArtifact]]],
) -> list[UUID]:
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for todo in todos:
        _append_optional_uuid(ordered, seen, todo.assigned_window_id)
        _append_optional_uuid(ordered, seen, todo.review_window_id)
        for _link, artifact in artifacts_by_todo.get(todo.id, []):
            _append_optional_uuid(ordered, seen, artifact.ephemeral_window_id)
            _append_optional_uuid(ordered, seen, artifact.source_window_id)
            _append_optional_uuid(ordered, seen, artifact.virtual_window_id)
    return ordered


def _todo_terminal_ids(
    todo: ProjectTodo,
    artifacts: list[tuple[object, TerminalArtifact]],
) -> list[UUID]:
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    _append_optional_uuid(ordered, seen, todo.assigned_window_id)
    _append_optional_uuid(ordered, seen, todo.review_window_id)
    for _link, artifact in artifacts:
        _append_optional_uuid(ordered, seen, artifact.ephemeral_window_id)
        _append_optional_uuid(ordered, seen, artifact.virtual_window_id)
        _append_optional_uuid(ordered, seen, artifact.source_window_id)
    return ordered


async def _terminal_titles_by_id(session: AsyncSession, window_ids: list[UUID]) -> dict[UUID, str]:
    if not window_ids:
        return {}
    rows = await session.execute(
        select(VirtualWindow.id, VirtualWindow.title).where(VirtualWindow.id.in_(window_ids))
    )
    return {window_id: title for window_id, title in rows}


def _append_optional_uuid(ordered: list[UUID], seen: set[UUID], value: UUID | None) -> None:
    if value is None or value in seen:
        return
    seen.add(value)
    ordered.append(value)
