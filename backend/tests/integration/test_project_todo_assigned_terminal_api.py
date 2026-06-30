from uuid import UUID, uuid4

import pytest

from app.models import Folder, ProjectTodo, VirtualWindow
from tests.integration.test_window_api_support import get_local_client_id


PROJECT_PATH = "/tmp/project-todo-assigned-terminal"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_list_project_todos_includes_assigned_terminal_summary(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Build tree board"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    folder_id = uuid4()
    window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(Folder(
            id=folder_id,
            client_id=UUID(client_id),
            name="Frontend UI",
            path="/Web Terminal ACP/Frontend UI",
        ))
        session.add(VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Board grouping terminal",
            folder_id=folder_id,
            cwd=PROJECT_PATH,
            shell_command="codex",
            summary="Implementing tree grouped project todos.",
            title_tags=["kanban", "frontend"],
        ))
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.agent_profile_id = "builtin/default"
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assigned_terminal = listed["assigned_terminal"]
    assert listed["assigned_window_id"] == str(window_id)
    assert assigned_terminal["id"] == str(window_id)
    assert assigned_terminal["title"] == "Board grouping terminal"
    assert assigned_terminal["summary"] == "Implementing tree grouped project todos."
    assert assigned_terminal["title_tags"] == ["kanban", "frontend"]
    assert assigned_terminal["topic_path"] == "/Web Terminal ACP/Frontend UI"
    assert assigned_terminal["git_worktree"] is None
    assert assigned_terminal["parent_window_id"] is None
    assert assigned_terminal["root_window_id"] is None
    assert assigned_terminal["derived_mode"] is None
    assert assigned_terminal["created_at"] is not None
    assert PROJECT_PATH in assigned_terminal["runtime_tags"]
    assert assigned_terminal["work_status"]["state"] == "LONG_IDLE"
