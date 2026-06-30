from __future__ import annotations

from uuid import UUID

import pytest

from app.contexts.windows.infrastructure.repository import create_window
from tests.integration.test_window_api_support import DbClient, get_local_client_id

pytest_plugins = ["tests.integration.test_window_api_support"]

PROJECT_PATH = "/tmp/project-todo-history"


@pytest.mark.asyncio
async def test_project_todo_history_records_versions_and_restores(db_client: DbClient) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Original title", "description": "Original description"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]

    initial_history = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/history",
        params={"project_path": PROJECT_PATH},
    )
    assert initial_history.status_code == 200
    initial_body = initial_history.json()
    assert [version["version_number"] for version in initial_body["versions"]] == [1]
    assert initial_body["versions"][0]["title"] == "Original title"
    assert initial_body["audit_logs"][0]["action"] == "created"
    assert initial_body["audit_logs"][0]["actor_type"] == "user"

    status_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"status": "BLOCKED"},
    )
    assert status_response.status_code == 200

    status_history = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/history",
        params={"project_path": PROJECT_PATH},
    )
    assert status_history.status_code == 200
    status_body = status_history.json()
    assert [version["version_number"] for version in status_body["versions"]] == [1]
    assert status_body["audit_logs"][0]["action"] == "updated"
    assert status_body["audit_logs"][0]["fields"] == ["status"]

    edit_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"title": "Edited title", "description": "Edited description"},
    )
    assert edit_response.status_code == 200

    edit_history = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/history",
        params={"project_path": PROJECT_PATH},
    )
    assert edit_history.status_code == 200
    edit_body = edit_history.json()
    assert [version["version_number"] for version in edit_body["versions"]] == [2, 1]
    assert edit_body["versions"][0]["title"] == "Edited title"
    assert edit_body["versions"][0]["description"] == "Edited description"
    assert edit_body["audit_logs"][0]["action"] == "updated"
    assert edit_body["audit_logs"][0]["fields"] == ["description", "title"]
    assert edit_body["audit_logs"][0]["from_version_number"] == 1
    assert edit_body["audit_logs"][0]["to_version_number"] == 2

    restore_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/versions/1/restore",
        params={"project_path": PROJECT_PATH},
    )
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["title"] == "Original title"
    assert restored["description"] == "Original description"

    restored_history = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/history",
        params={"project_path": PROJECT_PATH},
    )
    assert restored_history.status_code == 200
    restored_body = restored_history.json()
    assert [version["version_number"] for version in restored_body["versions"]] == [3, 2, 1]
    assert restored_body["versions"][0]["title"] == "Original title"
    assert restored_body["audit_logs"][0]["action"] == "restored"
    assert restored_body["audit_logs"][0]["fields"] == ["description", "title"]
    assert restored_body["audit_logs"][0]["from_version_number"] == 2
    assert restored_body["audit_logs"][0]["to_version_number"] == 3
    assert restored_body["audit_logs"][0]["restored_version_number"] == 1


@pytest.mark.asyncio
async def test_agent_ops_todo_patch_records_source_window_actor(db_client: DbClient) -> None:
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        source = await create_window(
            session,
            UUID(client_id),
            cwd=PROJECT_PATH,
            shell_command="codex",
            tmux_session="test_pool",
            tmux_window_id="@agent",
        )
        source_window_id = str(source.id)
        await session.commit()

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Agent editable"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]

    patch_response = await db_client.patch(
        f"/api/agent-ops/project-todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        headers={
            "X-Web-Terminal-Source-Client-Id": client_id,
            "X-Web-Terminal-Source-Window-Id": source_window_id,
        },
        json={"title": "Agent changed title"},
    )
    assert patch_response.status_code == 200

    history_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/history",
        params={"project_path": PROJECT_PATH},
    )
    assert history_response.status_code == 200
    latest_log = history_response.json()["audit_logs"][0]
    assert latest_log["action"] == "updated"
    assert latest_log["actor_type"] == "agent"
    assert latest_log["actor_id"] == source_window_id
    assert latest_log["source_window_id"] == source_window_id
