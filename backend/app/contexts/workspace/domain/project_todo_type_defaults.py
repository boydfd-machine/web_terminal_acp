from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


DEFAULT_PROJECT_TODO_TYPE_ID = "default"


@dataclass(frozen=True)
class ProjectTodoTypeDefault:
    record_id: UUID
    id: str
    name: str
    description: str
    agent: str | None
    agent_profile_id: str | None
    artifact_kinds: tuple[str, ...]
    dispatch_template: str


BUILTIN_PROJECT_TODO_TYPE_DEFAULTS: tuple[ProjectTodoTypeDefault, ...] = ()


DEFAULT_PROJECT_TODO_TYPE = ProjectTodoTypeDefault(
    record_id=UUID("00000000-0000-0000-0000-000000000001"),
    id=DEFAULT_PROJECT_TODO_TYPE_ID,
    name="Default",
    description="Default project todo card type.",
    agent=None,
    agent_profile_id=None,
    artifact_kinds=(),
    dispatch_template="",
)


def all_project_todo_type_defaults() -> tuple[ProjectTodoTypeDefault, ...]:
    return BUILTIN_PROJECT_TODO_TYPE_DEFAULTS
