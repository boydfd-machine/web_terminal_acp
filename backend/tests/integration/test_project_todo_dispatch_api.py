import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.contexts.workspace.application import project_todo_dispatch_after as dispatch_after_service
from app.models import AiSession, Event, EventSourceType, ProjectTodo, ProjectTodoStatus, VirtualWindow
from app.repositories.terminal_artifacts import create_terminal_artifact
from app.contexts.workspace.infrastructure.project_todos_repository import link_project_todo_artifact
from tests.integration.test_window_api_support import (
    codex_message_payload,
    codex_user_message_payload,
    get_local_client_id,
    wait_for_local_window_ready,
)


PROJECT_PATH = "/tmp/project-todos"
PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS = 5.0
pytest_plugins = ["tests.integration.test_window_api_support"]


async def _wait_for_dispatched_prompt_count(dispatched_prompts: list[dict[str, object]], count: int) -> None:
    for _ in range(200):
        if len(dispatched_prompts) >= count:
            return
        await asyncio.sleep(PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"dispatched prompt count did not reach {count}")


async def _wait_for_project_todo_status(
    db_client,
    todo_id: str,
    status: ProjectTodoStatus,
) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.status == status:
                return todo
        await asyncio.sleep(PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"project todo did not reach status {status.value}")


async def _wait_for_project_todo_stage(db_client, todo_id: str, stage: str) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.dispatch_stage == stage:
                return todo
        await asyncio.sleep(PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"project todo did not reach dispatch stage {stage}")


@pytest.mark.asyncio
async def test_dispatch_project_todo_creates_agent_window(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    dispatched_prompts: list[dict[str, object]] = []

    async def fake_dispatch_project_todo_prompt(**kwargs) -> None:
        dispatched_prompts.append({
            "window_id": str(kwargs["window_id"]),
            "prompt": kwargs["prompt"],
            "submit_prompt": kwargs["submit_prompt"],
        })

    monkeypatch.setattr(
        dispatch_after_service,
        "dispatch_project_todo_prompt",
        fake_dispatch_project_todo_prompt,
    )
    referenced_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Current project context",
            "description": "Keep settings local",
        },
    )
    assert referenced_response.status_code == 200
    referenced = referenced_response.json()
    referenced_window_id = UUID("00000000-0000-0000-0000-000000000101")
    referenced_artifact_window_id = UUID("00000000-0000-0000-0000-000000000102")
    referenced_artifact_id = None
    base_time = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        session.add_all(
            [
                VirtualWindow(
                    id=referenced_window_id,
                    client_id=UUID(client_id),
                    title="Context terminal",
                    cwd=PROJECT_PATH,
                    shell_command="codex",
                ),
                VirtualWindow(
                    id=referenced_artifact_window_id,
                    client_id=UUID(client_id),
                    title="Context artifact terminal",
                    cwd=PROJECT_PATH,
                    shell_command="codex",
                ),
            ]
        )
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="dispatch-reference-session",
            virtual_window_id=referenced_window_id,
        )
        session.add(ai_session)
        await session.flush()
        todo = await session.get(ProjectTodo, UUID(referenced["id"]))
        assert todo is not None
        todo.assigned_window_id = referenced_window_id
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=referenced_artifact_window_id,
            source_window_id=referenced_window_id,
            artifact_kind="agent_trace_graph",
            title="Context trace",
        )
        referenced_artifact_id = artifact.id
        await link_project_todo_artifact(session, todo, artifact.id, purpose="review")
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="dispatch-reference-session",
                    kind="response_item",
                    virtual_window_id=referenced_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload("Use description to configure settings"),
                    fingerprint="todo-dispatch-reference-user",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="dispatch-reference-session",
                    kind="response_item",
                    virtual_window_id=referenced_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload("Settings context is complete"),
                    fingerprint="todo-dispatch-reference-agent",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Implement settings tab", "description": "Use @[其它需求：$Current project context]"},
    )
    todo_id = create_response.json()["id"]

    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/dispatch",
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
    started = dispatch_response.json()
    assert started["status"] == "TODO"
    assert started["assigned_agent"] == "codex"
    assert started["assigned_window_id"] is None
    assert started["dispatch_stage"] == "STARTING"
    assert started["dispatch_error"] is None
    await _wait_for_dispatched_prompt_count(dispatched_prompts, 1)
    dispatched = await _wait_for_project_todo_status(db_client, todo_id, ProjectTodoStatus.dispatched)
    assert "Implement settings tab" in dispatched_prompts[0]["prompt"]
    assert "# References" in dispatched_prompts[0]["prompt"]
    assert "## Current project context Card" in dispatched_prompts[0]["prompt"]
    assert "### Sessions" in dispatched_prompts[0]["prompt"]
    assert "### artifacts" in dispatched_prompts[0]["prompt"]
    assert "### terminals" in dispatched_prompts[0]["prompt"]
    assert "Keep settings local" not in dispatched_prompts[0]["prompt"]
    assert "Use description to configure settings" in dispatched_prompts[0]["prompt"]
    assert "Settings context is complete" in dispatched_prompts[0]["prompt"]
    assert f"Context terminal ({referenced_window_id})" in dispatched_prompts[0]["prompt"]
    assert f"Context trace (artifact: {referenced_artifact_id})" in dispatched_prompts[0]["prompt"]
    assert f"Context artifact terminal ({referenced_artifact_window_id})" in dispatched_prompts[0]["prompt"]
    assert dispatched.assigned_window_id is not None
    assert dispatched.dispatch_stage is None
    assert dispatched.dispatch_error is None
    assert dispatched_prompts[0]["window_id"] == str(dispatched.assigned_window_id)
    assert dispatched_prompts[0]["submit_prompt"] is True
    window = await wait_for_local_window_ready(db_client, client_id, str(dispatched.assigned_window_id))
    assert window.cwd == PROJECT_PATH
    assert window.shell_command == "codex"

    child_create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Wire child settings UI",
            "description": "Build on the parent implementation.",
            "parent_todo_id": referenced["id"],
        },
    )
    child_todo_id = child_create_response.json()["id"]
    child_dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{child_todo_id}/dispatch",
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

    assert child_dispatch_response.status_code == 200
    await _wait_for_dispatched_prompt_count(dispatched_prompts, 2)
    child_prompt = dispatched_prompts[1]["prompt"]
    assert "# Parent card" in child_prompt
    assert "## Current project context Card" in child_prompt
    assert "Use description to configure settings" in child_prompt
    assert "# References" not in child_prompt

    compose_create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Prepare manual prompt"},
    )
    compose_todo_id = compose_create_response.json()["id"]
    compose_dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{compose_todo_id}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": None,
            },
            "dispatch_mode": "compose",
        },
    )

    assert compose_dispatch_response.status_code == 200
    compose_started = compose_dispatch_response.json()
    assert compose_started["status"] == "TODO"
    assert compose_started["dispatch_stage"] == "STARTING"
    assert compose_started["assigned_window_id"] is None
    await _wait_for_dispatched_prompt_count(dispatched_prompts, 3)
    compose_dispatched = await _wait_for_project_todo_status(
        db_client,
        compose_todo_id,
        ProjectTodoStatus.dispatched,
    )
    assert "Prepare manual prompt" in dispatched_prompts[2]["prompt"]
    assert compose_dispatched.assigned_window_id is not None
    assert dispatched_prompts[2]["window_id"] == str(compose_dispatched.assigned_window_id)
    assert dispatched_prompts[2]["submit_prompt"] is False


@pytest.mark.asyncio
async def test_dispatch_project_todo_stays_pending_until_prompt_dispatch_finishes(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Wait for agent work"},
    )
    todo_id = create_response.json()["id"]
    prompt_started = asyncio.Event()
    allow_prompt_finish = asyncio.Event()
    observed_status_before_prompt_finish: list[ProjectTodoStatus] = []
    observed_assigned_window_before_prompt_finish: list[UUID | None] = []
    observed_stage_before_prompt_finish: list[str | None] = []

    async def fake_dispatch_project_todo_prompt(**_kwargs) -> None:
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            assert todo is not None
            observed_status_before_prompt_finish.append(todo.status)
            observed_assigned_window_before_prompt_finish.append(todo.assigned_window_id)
            observed_stage_before_prompt_finish.append(todo.dispatch_stage)
        prompt_started.set()
        await allow_prompt_finish.wait()

    monkeypatch.setattr(dispatch_after_service, "dispatch_project_todo_prompt", fake_dispatch_project_todo_prompt)
    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/dispatch",
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
    started = dispatch_response.json()
    assert started["status"] == "TODO"
    assert started["assigned_window_id"] is None
    assert started["dispatch_stage"] == "STARTING"
    await asyncio.wait_for(prompt_started.wait(), timeout=PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS)
    assert observed_status_before_prompt_finish == [ProjectTodoStatus.todo]
    assert observed_assigned_window_before_prompt_finish[0] is not None
    assert observed_stage_before_prompt_finish == ["TERMINAL_READY"]

    allow_prompt_finish.set()
    dispatched = await _wait_for_project_todo_status(db_client, todo_id, ProjectTodoStatus.dispatched)
    assert dispatched.assigned_window_id is not None
    assert dispatched.dispatch_stage is None


@pytest.mark.asyncio
async def test_dispatch_project_todo_rejects_blocked_card(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)

    async def fake_dispatch_project_todo_prompt(**_kwargs) -> None:
        raise TimeoutError("agent did not start working")

    monkeypatch.setattr(dispatch_after_service, "dispatch_project_todo_prompt", fake_dispatch_project_todo_prompt)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Keep todo on failure", "status": "BLOCKED"},
    )
    todo_id = create_response.json()["id"]

    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/dispatch",
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

    assert dispatch_response.status_code == 409
    assert dispatch_response.json()["detail"] == "todo is blocked"
    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        assert todo.status == ProjectTodoStatus.blocked
        assert todo.assigned_window_id is None
        assert todo.dispatch_stage is None
        assert todo.dispatch_error is None
        assert todo.dispatched_at is None


@pytest.mark.asyncio
async def test_manual_status_move_cancels_queued_dependency_dispatch(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    dispatched_prompts: list[dict[str, object]] = []

    async def fake_dispatch_project_todo_prompt(**kwargs) -> None:
        dispatched_prompts.append({"window_id": str(kwargs["window_id"]), "prompt": kwargs["prompt"]})

    monkeypatch.setattr(dispatch_after_service, "dispatch_project_todo_prompt", fake_dispatch_project_todo_prompt)
    upstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Build API"},
    )
    downstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Wire UI"},
    )
    upstream_id = upstream_response.json()["id"]
    downstream_id = downstream_response.json()["id"]

    queued_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{downstream_id}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": None,
            },
            "dispatch_after_todo_ids": [upstream_id],
        },
    )
    assert queued_response.status_code == 200
    assert queued_response.json()["queued_dispatch"] is True

    cancel_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{downstream_id}",
        params={"project_path": PROJECT_PATH},
        json={"status": "TODO"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "TODO"
    assert cancel_response.json()["queued_dispatch"] is False

    upstream_done_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{upstream_id}",
        params={"project_path": PROJECT_PATH},
        json={"status": "AWAITING_REVIEW"},
    )
    assert upstream_done_response.status_code == 200
    assert dispatched_prompts == []

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    todos = {todo["id"]: todo for todo in list_response.json()["todos"]}
    downstream = todos[downstream_id]
    assert downstream["status"] == "TODO"
    assert downstream["queued_dispatch"] is False
    assert downstream["assigned_window_id"] is None
    assert downstream["dispatch_stage"] is None
