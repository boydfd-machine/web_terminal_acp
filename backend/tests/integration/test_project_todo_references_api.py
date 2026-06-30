import pytest

from tests.integration.test_window_api_support import get_local_client_id


PROJECT_PATH = "/tmp/project-todo-references"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_todo_description_resolves_referenced_cards(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    referenced_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Build API",
            "description": "Expose stable endpoints",
        },
    )
    assert referenced_response.status_code == 200
    referenced = referenced_response.json()

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Wire UI",
            "description": "Coordinate with @[其它需求：$Build API] before dispatch",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["referenced_todos"] == [
        {
            "id": referenced["id"],
            "title": "Build API",
            "description": "Expose stable endpoints",
            "status": "TODO",
        }
    ]

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    listed = {todo["title"]: todo for todo in list_response.json()["todos"]}
    assert listed["Wire UI"]["referenced_todos"][0]["id"] == referenced["id"]


@pytest.mark.asyncio
async def test_project_todo_description_resolves_id_references_after_title_change(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    referenced_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Build API",
            "description": "Expose stable endpoints",
        },
    )
    assert referenced_response.status_code == 200
    referenced = referenced_response.json()

    rename_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{referenced['id']}",
        params={"project_path": PROJECT_PATH},
        json={"title": "Build API v2"},
    )
    assert rename_response.status_code == 200

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Bug follow-up",
            "description": f"Regression from @[其它需求：$Build API|{referenced['id']}]",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["referenced_todos"] == [
        {
            "id": referenced["id"],
            "title": "Build API v2",
            "description": "Expose stable endpoints",
            "status": "TODO",
        }
    ]
