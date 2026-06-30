import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.contexts.workspace.application import project_todo_dispatch_after as dispatch_after_service
from app.models import AiSession, Event, EventSourceType, ProjectTodo, ProjectTodoStatus, VirtualWindow
from tests.integration.test_window_api_support import (
    codex_message_payload,
    codex_user_message_payload,
    get_local_client_id,
)


PROJECT_PATH = "/tmp/project-todos"
ASYNC_TEST_TIMEOUT_SECONDS = 5.0
pytest_plugins = ["tests.integration.test_window_api_support"]


async def _wait_for_dispatched_prompt(dispatched_prompts: list[str]) -> str:
    for _ in range(200):
        if dispatched_prompts:
            return dispatched_prompts[0]
        await asyncio.sleep(ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError("project todo prompt was not dispatched")


async def _wait_for_project_todo_status(db_client, todo_id: str, status: ProjectTodoStatus) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.status == status:
                return todo
        await asyncio.sleep(ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"project todo did not reach status {status.value}")


@pytest.mark.asyncio
async def test_dispatch_project_todo_limits_parent_agent_record_context(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    dispatched_prompts: list[str] = []

    async def fake_dispatch_project_todo_prompt(**kwargs) -> None:
        dispatched_prompts.append(kwargs["prompt"])

    monkeypatch.setattr(dispatch_after_service, "dispatch_project_todo_prompt", fake_dispatch_project_todo_prompt)
    parent_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Parent with heavy agent records"},
    )
    assert parent_response.status_code == 200
    parent = parent_response.json()
    parent_window_id = UUID("00000000-0000-0000-0000-000000000201")
    base_time = datetime.now(timezone.utc)
    long_user_input = "PARENT_USER_HEAD " + ("u" * 120_000) + " PARENT_USER_TAIL"
    long_agent_output = "PARENT_AGENT_HEAD " + ("a" * 120_000) + " PARENT_AGENT_TAIL"

    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=parent_window_id,
                client_id=UUID(client_id),
                title="Heavy parent terminal",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="parent-heavy-records-session",
            virtual_window_id=parent_window_id,
        )
        session.add(ai_session)
        await session.flush()
        todo = await session.get(ProjectTodo, UUID(parent["id"]))
        assert todo is not None
        todo.assigned_window_id = parent_window_id
        events = []
        for index in range(12):
            user_time = base_time + timedelta(milliseconds=index * 2)
            events.extend([
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="parent-heavy-records-session",
                    kind="response_item",
                    virtual_window_id=parent_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload(f"{long_user_input} turn {index}"),
                    fingerprint=f"todo-parent-heavy-user-{index}",
                    created_at=user_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="parent-heavy-records-session",
                    kind="response_item",
                    virtual_window_id=parent_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload(f"{long_agent_output} turn {index}"),
                    fingerprint=f"todo-parent-heavy-agent-{index}",
                    created_at=user_time + timedelta(milliseconds=1),
                ),
            ])
        session.add_all(events)
        await session.commit()

    child_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Child task stays intact",
            "description": "The child dispatch request must not disappear.",
            "parent_todo_id": parent["id"],
        },
    )
    assert child_response.status_code == 200
    child_id = child_response.json()["id"]
    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{child_id}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": None,
            },
        },
    )

    assert dispatch_response.status_code == 200
    prompt = await _wait_for_dispatched_prompt(dispatched_prompts)
    await _wait_for_project_todo_status(db_client, child_id, ProjectTodoStatus.dispatched)
    assert "Todo: Child task stays intact" in prompt
    assert "The child dispatch request must not disappear." in prompt
    assert "## Parent with heavy agent records Card" in prompt
    assert "PARENT_USER_HEAD" in prompt
    assert "PARENT_AGENT_TAIL" in prompt
    assert "[truncated " in prompt
    assert "showing most recent" in prompt
    assert len(prompt) < 90_000
