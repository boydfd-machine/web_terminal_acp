from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, or_, select

from app.models import (
    Folder,
    ProjectTodo,
    ProjectTodoDependency,
    ProjectTodoType,
    VirtualWindow,
)
from tests.integration.test_window_api_support import get_local_client_id


PROJECT_PATH = "/tmp/project-todos-move-source"
TARGET_PROJECT_PATH = "/tmp/project-todos-move-target"
pytest_plugins = ["tests.integration.test_window_api_support"]


async def _create_visible_project(db_client, client_id: str, project_path: str) -> None:
    async with db_client.session_factory() as session:
        folder = Folder(
            client_id=UUID(client_id),
            name=f"move-target-{uuid4().hex}",
            path=f"/move-target-{uuid4().hex}",
        )
        session.add(folder)
        await session.flush()
        session.add(
            VirtualWindow(
                client_id=UUID(client_id),
                title=f"Window for {project_path}",
                folder_id=folder.id,
                cwd=project_path,
                shell_command="codex",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_move_project_todo_moves_todo_card_to_existing_project(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    await _create_visible_project(db_client, client_id, TARGET_PROJECT_PATH)
    async with db_client.session_factory() as session:
        session.add(
            ProjectTodoType(
                id="bug",
                scope="project",
                client_id=UUID(client_id),
                project_path=PROJECT_PATH,
                name="Bug",
                description="Fix a defect.",
            )
        )
        await session.commit()

    target_existing_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": TARGET_PROJECT_PATH},
        json={"title": "Existing target card"},
    )
    assert target_existing_response.status_code == 200
    target_existing = target_existing_response.json()

    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Move me", "todo_type_id": "bug"},
    )
    assert source_response.status_code == 200
    source = source_response.json()
    child_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Child card", "parent_todo_id": source["id"]},
    )
    assert child_response.status_code == 200
    other_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Related card"},
    )
    assert other_response.status_code == 200
    other = other_response.json()

    async with db_client.session_factory() as session:
        session.add_all([
            ProjectTodoDependency(
                client_id=UUID(client_id),
                project_path=PROJECT_PATH,
                project_todo_id=UUID(source["id"]),
                depends_on_todo_id=UUID(other["id"]),
            ),
            ProjectTodoDependency(
                client_id=UUID(client_id),
                project_path=PROJECT_PATH,
                project_todo_id=UUID(other["id"]),
                depends_on_todo_id=UUID(source["id"]),
            ),
        ])
        await session.commit()

    move_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{source['id']}/move-project",
        params={"project_path": PROJECT_PATH},
        json={"project_path": TARGET_PROJECT_PATH},
    )
    assert move_response.status_code == 200
    moved = move_response.json()
    assert moved["project_path"] == TARGET_PROJECT_PATH
    assert moved["parent_todo_id"] is None
    assert moved["todo_type"]["id"] == "default"
    assert moved["sort_order"] == target_existing["sort_order"] + 1

    source_list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert source_list_response.status_code == 200
    assert source["id"] not in {todo["id"] for todo in source_list_response.json()["todos"]}
    target_list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": TARGET_PROJECT_PATH},
    )
    assert target_list_response.status_code == 200
    assert source["id"] in {todo["id"] for todo in target_list_response.json()["todos"]}

    async with db_client.session_factory() as session:
        child = await session.get(ProjectTodo, UUID(child_response.json()["id"]))
        assert child is not None
        assert child.parent_todo_id is None
        dependency_count = await session.scalar(
            select(func.count(ProjectTodoDependency.id)).where(
                or_(
                    ProjectTodoDependency.project_todo_id == UUID(source["id"]),
                    ProjectTodoDependency.depends_on_todo_id == UUID(source["id"]),
                )
            )
        )
        assert dependency_count == 0


@pytest.mark.asyncio
async def test_move_project_todo_rejects_non_todo_status(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    await _create_visible_project(db_client, client_id, TARGET_PROJECT_PATH)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Already done"},
    )
    assert create_response.status_code == 200
    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{create_response.json()['id']}",
        params={"project_path": PROJECT_PATH},
        json={"status": "DONE"},
    )
    assert patch_response.status_code == 200

    move_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{create_response.json()['id']}/move-project",
        params={"project_path": PROJECT_PATH},
        json={"project_path": TARGET_PROJECT_PATH},
    )
    assert move_response.status_code == 409
    assert move_response.json()["detail"] == "only TODO cards can move projects"


@pytest.mark.asyncio
async def test_move_project_todo_rejects_queued_todo(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    await _create_visible_project(db_client, client_id, TARGET_PROJECT_PATH)
    upstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Upstream"},
    )
    assert upstream_response.status_code == 200
    todo_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Queued downstream"},
    )
    assert todo_response.status_code == 200
    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_response.json()['id']}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {"agent": "codex", "command": "codex", "config": None, "profile_id": None},
            "dispatch_after_todo_ids": [upstream_response.json()["id"]],
        },
    )
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["queued_dispatch"] is True

    move_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_response.json()['id']}/move-project",
        params={"project_path": PROJECT_PATH},
        json={"project_path": TARGET_PROJECT_PATH},
    )
    assert move_response.status_code == 409
    assert move_response.json()["detail"] == "only TODO cards can move projects"


@pytest.mark.asyncio
async def test_move_project_todo_rejects_missing_target_project(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Move nowhere"},
    )
    assert create_response.status_code == 200

    move_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{create_response.json()['id']}/move-project",
        params={"project_path": PROJECT_PATH},
        json={"project_path": TARGET_PROJECT_PATH},
    )
    assert move_response.status_code == 404
    assert move_response.json()["detail"] == "target project not found"
