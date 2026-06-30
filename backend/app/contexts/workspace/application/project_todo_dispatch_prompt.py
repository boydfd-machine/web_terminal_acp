from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.application.project_todo_dispatch import (
    ProjectTodoPromptReference,
    append_project_todo_reference_context,
    build_project_todo_prompt,
    build_project_todo_template_prompt,
)
from app.contexts.workspace.application.project_todo_reference_context import (
    prompt_references_for_project_todos,
)
from app.contexts.workspace.application.project_todo_repository import (
    parent_project_todos_for_todos,
    referenced_project_todos_for_todos,
)
from app.contexts.workspace.application.project_todo_types import get_project_todo_type
from app.models import ProjectTodo


async def build_dispatch_prompt_for_project_todo(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_path: str,
    todo: ProjectTodo,
    payload_prompt: str | None,
    output_language: str | None = None,
) -> str:
    referenced_todos = (await referenced_project_todos_for_todos(session, [todo])).get(todo.id, [])
    parent_todos = await _parent_todo_chain(session, todo)
    todo_type = await get_project_todo_type(session, client_id, project_path, todo.todo_type_id)
    return _dispatch_prompt_for_todo(
        todo,
        project_path=project_path,
        payload_prompt=payload_prompt,
        output_language=output_language,
        dispatch_template=todo_type.dispatch_template if todo_type is not None else None,
        parent_todos=await prompt_references_for_project_todos(session, parent_todos),
        referenced_todos=await prompt_references_for_project_todos(session, referenced_todos),
    )


async def _parent_todo_chain(
    session: AsyncSession,
    todo: ProjectTodo,
) -> list[ProjectTodo]:
    parents: list[ProjectTodo] = []
    current = todo
    seen_ids: set[UUID] = {todo.id}
    while current.parent_todo_id is not None and current.parent_todo_id not in seen_ids:
        seen_ids.add(current.parent_todo_id)
        parent = (await parent_project_todos_for_todos(session, [current])).get(current.parent_todo_id)
        if parent is None:
            break
        parents.append(parent)
        current = parent
    return parents


def _dispatch_prompt_for_todo(
    todo: ProjectTodo,
    *,
    project_path: str,
    payload_prompt: str | None,
    output_language: str | None,
    dispatch_template: str | None,
    parent_todos: list[ProjectTodoPromptReference],
    referenced_todos: list[ProjectTodoPromptReference],
) -> str:
    input_artifact_ids = _todo_input_artifact_ids(todo)
    if payload_prompt:
        return append_project_todo_reference_context(
            _append_input_artifact_context(
                payload_prompt,
                input_artifact_ids,
                project_path=project_path,
            ),
            referenced_todos,
            parent_todos=parent_todos,
            output_language=output_language,
        )
    if dispatch_template:
        prompt = build_project_todo_template_prompt(
            template=dispatch_template,
            project_path=project_path,
            title=todo.title,
            description=todo.description,
            todo_type_id=todo.todo_type_id,
            artifact_kinds=todo.artifact_kinds_json or [],
            input_artifact_ids=input_artifact_ids,
            output_language=output_language,
        )
        return append_project_todo_reference_context(
            _append_input_artifact_context(
                prompt,
                input_artifact_ids,
                project_path=project_path,
            ),
            referenced_todos,
            parent_todos=parent_todos,
        )
    prompt = build_project_todo_prompt(
        project_path=project_path,
        title=todo.title,
        description=todo.description,
        output_language=output_language,
        parent_todos=parent_todos,
        referenced_todos=referenced_todos,
    )
    return _append_input_artifact_context(
        prompt,
        input_artifact_ids,
        project_path=project_path,
    )


def _todo_input_artifact_ids(todo: ProjectTodo) -> list[str]:
    value = getattr(todo, "input_artifact_ids_json", None)
    return value if isinstance(value, list) else []


def _append_input_artifact_context(prompt: str, input_artifact_ids: list[str], *, project_path: str) -> str:
    if not input_artifact_ids:
        return prompt
    artifact_lines = "\n".join(f"- {artifact_id}" for artifact_id in input_artifact_ids)
    section = (
        "# Input artifacts\n\n"
        "These project-level artifact IDs are available as task context:\n"
        f"{artifact_lines}\n\n"
        "Use the web-terminal-acp-ops skill to read them when needed, for example:\n"
        "`python3 scripts/web-terminal-acp-ops.py --compact read-artifact "
        "<client-id> <window-id> <artifact-id> "
        f"--artifact-scope project --project-path {project_path}`"
    )
    return f"{prompt.rstrip()}\n\n{section}"
