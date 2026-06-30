from app.contexts.workspace.domain.project_todo_type_defaults import (
    BUILTIN_PROJECT_TODO_TYPE_DEFAULTS,
    all_project_todo_type_defaults,
)


def test_project_todo_type_defaults_expose_no_builtin_seed_types() -> None:
    assert BUILTIN_PROJECT_TODO_TYPE_DEFAULTS == ()
    assert all_project_todo_type_defaults() == ()
