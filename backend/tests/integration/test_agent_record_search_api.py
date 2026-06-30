from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.models import AiSession, Event, EventSourceType, ProjectTodo, ProjectTodoStatus
from tests.integration.test_window_api_support import *  # noqa: F403


@pytest.mark.asyncio
async def test_window_agent_record_search_is_window_scoped_and_projected(db_client):
    client_id = await get_local_client_id(db_client)
    first_window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    second_window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    first_window_id = UUID(first_window_response.json()["id"])
    second_window_id = UUID(second_window_response.json()["id"])

    async with db_client.session_factory() as session:
        first_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-window-1",
            virtual_window_id=first_window_id,
        )
        second_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-window-2",
            virtual_window_id=second_window_id,
        )
        session.add_all([first_session, second_session])
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-window-1",
                    kind="response_item",
                    virtual_window_id=first_window_id,
                    ai_session_id=first_session.id,
                    payload_json=codex_message_payload("Scoped llama result"),
                    fingerprint="agent-record-search-window-1",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-window-2",
                    kind="response_item",
                    virtual_window_id=second_window_id,
                    ai_session_id=second_session.id,
                    payload_json=codex_message_payload("Other llama result"),
                    fingerprint="agent-record-search-window-2",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{first_window_id}/agent-record/search",
        params={"q": "llama"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "window"
    assert body["total"] == 1
    assert body["results"][0]["window_id"] == str(first_window_id)
    assert body["results"][0]["provider"] == "codex"
    assert body["results"][0]["message"]["body"] == "Scoped llama result"
    assert "payload_json" not in body["results"][0]["message"]
    assert body["results"][0]["matches"] == [{"field": "body", "start": 7, "end": 12}]


@pytest.mark.asyncio
async def test_client_agent_record_search_is_explicit_global_scope(db_client):
    client_id = await get_local_client_id(db_client)
    first_window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    second_window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    first_window_id = UUID(first_window_response.json()["id"])
    second_window_id = UUID(second_window_response.json()["id"])

    async with db_client.session_factory() as session:
        first_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="global-codex-1",
            virtual_window_id=first_window_id,
        )
        second_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="global-codex-2",
            virtual_window_id=second_window_id,
        )
        session.add_all([first_session, second_session])
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="global-codex-1",
                    kind="response_item",
                    virtual_window_id=first_window_id,
                    ai_session_id=first_session.id,
                    payload_json=codex_message_payload("Global alpaca one"),
                    fingerprint="agent-record-global-search-1",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="global-codex-2",
                    kind="response_item",
                    virtual_window_id=second_window_id,
                    ai_session_id=second_session.id,
                    payload_json=codex_message_payload("Global alpaca two"),
                    fingerprint="agent-record-global-search-2",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/agent-record/search",
        params={"q": "alpaca"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "global"
    assert body["total"] == 2
    assert {result["window_id"] for result in body["results"]} == {
        str(first_window_id),
        str(second_window_id),
    }


@pytest.mark.asyncio
async def test_project_todo_search_returns_kanban_card_jump_metadata(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        session.add_all(
            [
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/tmp/project-alpha",
                    title="Optimize llama search card",
                    description="Keep agent record search readable",
                    status=ProjectTodoStatus.todo,
                    sort_order=1,
                    assigned_agent="codex",
                ),
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/tmp/project-beta",
                    title="Unrelated card",
                    description="No relevant text",
                    status=ProjectTodoStatus.todo,
                    sort_order=2,
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/search",
        params={"q": "llama"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    [result] = body["results"]
    assert result["project_path"] == "/tmp/project-alpha"
    assert result["title"] == "Optimize llama search card"
    assert result["status"] == "TODO"
    assert result["matches"] == [{"field": "title", "start": 9, "end": 14}]


@pytest.mark.asyncio
async def test_project_todo_search_can_filter_by_project_path(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        session.add_all(
            [
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/tmp/project-alpha",
                    title="Shared search card alpha",
                    description="Same keyword",
                    status=ProjectTodoStatus.todo,
                    sort_order=1,
                ),
                ProjectTodo(
                    client_id=UUID(client_id),
                    project_path="/tmp/project-beta",
                    title="Shared search card beta",
                    description="Same keyword",
                    status=ProjectTodoStatus.todo,
                    sort_order=2,
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/search",
        params={"q": "shared", "project_path": "/tmp/project-beta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["project_path"] == "/tmp/project-beta"
