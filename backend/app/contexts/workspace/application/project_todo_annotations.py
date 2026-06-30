from __future__ import annotations

from app.models import ProjectTodo

MAX_PROJECT_TODO_DESCRIPTION_LENGTH = 65536
PROJECT_TODO_ANNOTATION_SEPARATOR = "\n\n---\n\n"


def append_project_todo_annotation(todo: ProjectTodo, annotation: str) -> None:
    normalized = annotation.strip()
    if not normalized:
        raise ValueError("annotation is required")
    current = (todo.description or "").strip()
    next_description = (
        f"{current}{PROJECT_TODO_ANNOTATION_SEPARATOR}{normalized}"
        if current
        else normalized
    )
    if len(next_description) > MAX_PROJECT_TODO_DESCRIPTION_LENGTH:
        raise ValueError("todo description would exceed 65536 characters")
    todo.description = next_description
