from uuid import UUID

import pytest

from app.models import ProjectTodo
from tests.integration.test_window_api_support import get_local_client_id


PROJECT_PATH = "/tmp/project-todos-long-description"
LONG_DESCRIPTION = "测" * 100_000

pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_todo_create_and_patch_accept_100k_description(db_client) -> None:
    client_id = await get_local_client_id(db_client)

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Long dispatch context",
            "description": LONG_DESCRIPTION,
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    todo_id = created["id"]
    assert created["description"] == LONG_DESCRIPTION

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["id"] == todo_id
    assert "description" not in listed

    updated_description = f"{LONG_DESCRIPTION}\n补充校验路径"
    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"description": updated_description},
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == updated_description

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        assert todo.description == updated_description
