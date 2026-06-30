from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.models import Event, EventSourceType, ProjectTodo, VirtualWindow
from tests.integration.test_window_api_support import (
    codex_message_payload,
    get_local_client_id,
)


PROJECT_PATH = "/tmp/project-todo-list-agent-status"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_todo_list_includes_cached_assigned_agent_work_status(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Show assigned agent status"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    activity_at = datetime.now(timezone.utc)

    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Assigned agent",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": "codex exec 'fix'", "sequence": 1},
                    fingerprint="project-todo-list-agent-command",
                    created_at=activity_at - timedelta(seconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-working",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    payload_json=codex_message_payload("Still working", timestamp=activity_at),
                    fingerprint="project-todo-list-agent-status-working",
                    created_at=activity_at,
                ),
            ]
        )
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["assigned_terminal"]["id"] == str(window_id)
    assert listed["assigned_terminal"]["work_status"]["state"] == "WORKING"
