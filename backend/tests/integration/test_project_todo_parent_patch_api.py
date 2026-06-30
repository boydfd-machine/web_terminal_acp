from __future__ import annotations

import pytest
from tests.integration.test_window_api_support import get_local_client_id


PROJECT_PATH = "/tmp/project-todo-parent-patch"
pytest_plugins = ["tests.integration.test_window_api_support"]


async def _create_todo(db_client, client_id: str, title: str, **payload) -> dict:
    response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": title, **payload},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_patch_project_todo_can_change_and_clear_parent_before_dispatch(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    first_parent = await _create_todo(db_client, client_id, "Original parent")
    second_parent = await _create_todo(db_client, client_id, "Replacement parent")
    child = await _create_todo(
        db_client,
        client_id,
        "Child task",
        parent_todo_id=first_parent["id"],
    )

    change_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{child['id']}",
        params={"project_path": PROJECT_PATH},
        json={"parent_todo_id": second_parent["id"]},
    )

    assert change_response.status_code == 200
    changed = change_response.json()
    assert changed["parent_todo_id"] == second_parent["id"]
    assert changed["parent_todo"]["title"] == "Replacement parent"

    clear_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{child['id']}",
        params={"project_path": PROJECT_PATH},
        json={"parent_todo_id": None},
    )

    assert clear_response.status_code == 200
    cleared = clear_response.json()
    assert cleared["parent_todo_id"] is None
    assert cleared["parent_todo"] is None


@pytest.mark.asyncio
async def test_patch_project_todo_rejects_parent_change_after_dispatch(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    parent = await _create_todo(db_client, client_id, "Parent")
    child = await _create_todo(db_client, client_id, "Child task")

    # Set through the public API so the stored status matches normal status transitions.
    patch_status_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{child['id']}",
        params={"project_path": PROJECT_PATH},
        json={"status": "DISPATCHED"},
    )
    assert patch_status_response.status_code == 200

    parent_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{child['id']}",
        params={"project_path": PROJECT_PATH},
        json={"parent_todo_id": parent["id"]},
    )

    assert parent_response.status_code == 409
    assert parent_response.json()["detail"] == "parent selection is locked"


@pytest.mark.asyncio
async def test_patch_project_todo_rejects_parent_cycle(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    parent = await _create_todo(db_client, client_id, "Parent")
    child = await _create_todo(db_client, client_id, "Child task", parent_todo_id=parent["id"])

    cycle_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{parent['id']}",
        params={"project_path": PROJECT_PATH},
        json={"parent_todo_id": child["id"]},
    )

    assert cycle_response.status_code == 400
    assert cycle_response.json()["detail"] == "parent todo would create a cycle"
