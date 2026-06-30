from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.contexts.workspace.infrastructure.project_todo_list_queries import project_todos_for_project_statement


def test_project_todo_list_query_uses_narrow_board_columns() -> None:
    statement = project_todos_for_project_statement(uuid4(), "/repo")

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "project_todos.description" in compiled
    assert "project_todos.dispatch_stage" in compiled
    assert "project_todos.dispatch_prompt" not in compiled
    assert "project_todos.review_prompt" not in compiled
    assert "project_todos.last_agent_launch_json" not in compiled
