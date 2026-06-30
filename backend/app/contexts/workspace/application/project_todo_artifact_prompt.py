from __future__ import annotations

from typing import Any

from app.models import ProjectTodo
from app.contexts.workspace.application.project_todo_prompt_references import single_line_output_language


def requested_artifact_context_metadata(todo: ProjectTodo, encoded_kind: str) -> dict[str, Any]:
    return {
        "project_todo_title": todo.title,
        "project_todo_description": todo.description or "",
        "project_todo_dispatch_prompt": todo.dispatch_prompt or "",
        "project_todo_requested_artifact": encoded_kind,
        "project_todo_project_path": todo.project_path,
        "output_language": single_line_output_language(todo.dispatch_output_language),
    }


def build_requested_artifact_prompt(todo: ProjectTodo, encoded_kind: str) -> str:
    parts = [
        "Generate the requested artifact for this project todo.",
        f"Project path: {todo.project_path}",
        f"Todo: {todo.title}",
        f"Requested artifact: {encoded_kind}",
    ]
    if todo.description:
        parts.extend(["", "Todo description:", todo.description])
    if todo.dispatch_prompt:
        parts.extend(["", "Implementation dispatch prompt:", todo.dispatch_prompt])
    parts.extend(
        [
            "",
            "Use the todo context as source input. Preserve unknowns explicitly instead of inventing reviewed facts.",
        ]
    )
    return "\n".join(parts)
