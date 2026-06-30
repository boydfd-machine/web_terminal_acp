import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.models import (
    Event,
    EventSourceType,
    GitWorktreeRun,
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoStatus,
    ProjectTodoType,
    TerminalArtifactStatus,
    VirtualWindow,
)
from app.contexts.workspace.application import project_todo_dispatch_after as dispatch_after_service
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_succeeded
from app.services.summary_scheduler import schedule_summary_after_agent_activity
from tests.integration.test_window_api_support import (
    codex_completion_payload,
    get_local_client_id,
    wait_for_local_window_ready,
)


PROJECT_PATH = "/tmp/project-todos"
PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS = 5.0
pytest_plugins = ["tests.integration.test_window_api_support"]


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
async def test_project_todo_list_items_include_linked_artifact_agents(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Show artifact agent"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    implementation_window_id = uuid4()
    artifact_window_id = uuid4()
    async with db_client.session_factory() as session:
        implementation_window = VirtualWindow(
            id=implementation_window_id,
            client_id=UUID(client_id),
            title="Implementation",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        artifact_window = VirtualWindow(
            id=artifact_window_id,
            client_id=UUID(client_id),
            title="Artifact agent",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add_all([implementation_window, artifact_window])
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = implementation_window_id
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=implementation_window_id,
            source_window_id=implementation_window_id,
            artifact_kind="agent_trace_graph",
            title="Show artifact agent - Agent Trace Graph",
        )
        artifact.status = TerminalArtifactStatus.running
        artifact.ephemeral_window_id = artifact_window_id
        db_link = ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=implementation_window_id,
            purpose="todo_artifact",
        )
        session.add(db_link)
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    [linked] = listed["artifacts"]
    assert linked["artifact_kind"] == "agent_trace_graph"
    assert linked["status"] == "RUNNING"
    assert linked["ephemeral_window_id"] == str(artifact_window_id)
    assert linked["agent_name"] == "Artifact agent"

@pytest.mark.asyncio
async def test_project_todo_dispatch_uses_type_template_when_prompt_omitted(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    type_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todo-types/system",
        json={
            "id": "deepresearch",
            "name": "Deep research",
            "agent": "codex",
            "agent_profile_id": "builtin/developer",
            "artifact_kinds": ["agent_trace_graph"],
            "dispatch_template": "Research task: {{ title }}\nProject: {{ project_path }}\nDetails: {{ description }}",
        },
    )
    assert type_response.status_code == 200
    todo_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Compare markdown renderers",
            "description": "Focus on security and tables.",
            "todo_type_id": "deepresearch",
        },
    )
    todo_id = todo_response.json()["id"]
    upstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Pick report audience"},
    )
    upstream_id = upstream_response.json()["id"]
    queued_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": "builtin/developer",
            },
            "dispatch_after_todo_ids": [upstream_id],
        },
    )

    assert queued_response.status_code == 200
    queued = queued_response.json()
    assert queued["queued_dispatch"] is True
    assert queued["dispatch_prompt"].startswith("System language for agent response: 中文.")
    assert (
        "Research task: Compare markdown renderers\n"
        f"Project: {PROJECT_PATH}\n"
        "Details: Focus on security and tables."
    ) in queued["dispatch_prompt"]

@pytest.mark.asyncio
async def test_project_todo_types_endpoint_includes_project_scoped_read_only_types(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        session.add(
            ProjectTodoType(
                id="bug",
                scope="project",
                client_id=UUID(client_id),
                project_path=PROJECT_PATH,
                name="Bug",
                description="Fix a defect.",
                agent="claude",
                agent_profile_id="bug-profile",
            )
        )
        await session.commit()
    response = await db_client.get(
        f"/api/clients/{client_id}/projects/todo-types",
        params={"project_path": PROJECT_PATH},
    )

    assert response.status_code == 200
    assert response.json()["todo_types"][-1] == {
        "id": "bug",
        "scope": "project",
        "client_id": client_id,
        "project_path": PROJECT_PATH,
        "name": "Bug",
        "description": "Fix a defect.",
        "agent": "claude",
        "agent_profile_id": "bug-profile",
        **{"artifact_kinds": [], "dispatch_template": None},
        "created_at": response.json()["todo_types"][-1]["created_at"],
        "updated_at": response.json()["todo_types"][-1]["updated_at"],
    }

@pytest.mark.asyncio
async def test_list_project_todos_returns_newest_board_additions_first(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    first_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "First board card"},
    )
    assert first_response.status_code == 200
    first = first_response.json()
    second_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Second board card"},
    )
    assert second_response.status_code == 200
    second = second_response.json()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    listed = list_response.json()["todos"]
    assert [todo["id"] for todo in listed[:2]] == [second["id"], first["id"]]

@pytest.mark.asyncio
async def test_create_project_todo_from_page_review_card_links_source_artifact(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    window_id = uuid4()
    async with db_client.session_factory() as session:
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Settings review",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add(window)
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="page_review_cards",
            title="Settings page review",
        )
        await mark_artifact_succeeded(
            session,
            artifact,
            content_json={
                "artifact_kind": "page_review_cards",
                "title": "Settings page review",
                "page": "/settings",
                "review_scope": "Settings empty state",
                "executive_summary": "One high-value improvement.",
                "cards": [
                    {
                        "id": "PRC-001",
                        "title": "Clarify empty state",
                        "type": "interaction",
                        "priority": "P1",
                        "severity": "high",
                        "user_value": "Users know how to continue.",
                        "problem": "The settings panel is blank when no data exists.",
                        "proposal": "Show an empty state with a primary setup action.",
                        "evidence": [{"label": "Observation", "detail": "Blank settings panel"}],
                        "acceptance_criteria": ["Primary setup action is visible."],
                        "test_notes": ["Open settings with no configured data."],
                    }
                ],
            },
            display_html="<html><body>review</body></html>",
        )
        artifact_id = artifact.id
        await session.commit()

    response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/from-page-review-card",
        params={"project_path": PROJECT_PATH},
        json={"artifact_id": str(artifact_id), "card_id": "PRC-001"},
    )

    assert response.status_code == 200
    created = response.json()
    assert created["title"] == "[P1] Clarify empty state"
    assert created["status"] == "TODO"
    assert "Card id: PRC-001" in created["description"]
    assert "Proposal:\nShow an empty state with a primary setup action." in created["description"]
    assert created["artifacts"] == [
        {
            "id": created["artifacts"][0]["id"],
            "artifact_id": str(artifact_id),
            "client_id": client_id,
            "window_id": str(window_id),
            "source_window_id": str(window_id),
            "ephemeral_window_id": None,
            "review_run_id": None,
            "created_by_window_id": str(window_id),
            "artifact_scope": "terminal",
            "project_path": None,
            "title": "Settings page review",
            "artifact_kind": "page_review_cards",
            "status": "SUCCEEDED",
            "purpose": "page_review",
            "agent_name": None,
            "agent_status": None,
            "metadata_json": None,
            "last_error": None,
            "started_at": None,
            "completed_at": created["artifacts"][0]["completed_at"],
            "created_at": created["artifacts"][0]["created_at"],
            "updated_at": created["artifacts"][0]["updated_at"],
        }
    ]

@pytest.mark.asyncio
async def test_dispatch_project_todo_after_upstream_completion(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    dispatched_prompts: list[dict[str, object]] = []
    prompt_started = asyncio.Event()
    allow_prompt_finish = asyncio.Event()

    async def fake_dispatch_project_todo_prompt(**kwargs) -> None:
        dispatched_prompts.append({
            "window_id": str(kwargs["window_id"]),
            "prompt": kwargs["prompt"],
            "submit_prompt": kwargs["submit_prompt"],
        })
        prompt_started.set()
        await allow_prompt_finish.wait()

    monkeypatch.setattr(
        dispatch_after_service,
        "dispatch_project_todo_prompt",
        fake_dispatch_project_todo_prompt,
    )
    first_upstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Build API"},
    )
    second_upstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Prepare data"},
    )
    downstream_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Wire UI"},
    )
    first_upstream_id = first_upstream_response.json()["id"]
    second_upstream_id = second_upstream_response.json()["id"]
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
            "dispatch_after_todo_ids": [first_upstream_id, second_upstream_id],
        },
    )

    assert queued_response.status_code == 200
    queued = queued_response.json()
    assert queued["status"] == "TODO"
    assert queued["queued_dispatch"] is True
    assert queued["assigned_window_id"] is None
    assert queued["dispatch_stage"] is None
    assert queued["dispatch_error"] is None
    assert {dependency["id"] for dependency in queued["dependencies"]} == {
        first_upstream_id,
        second_upstream_id,
    }
    assert dispatched_prompts == []

    waiting_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{first_upstream_id}",
        params={"project_path": PROJECT_PATH},
        json={"status": "AWAITING_REVIEW"},
    )

    assert waiting_response.status_code == 200
    first_upstream = waiting_response.json()
    assert first_upstream["dependents"][0]["id"] == downstream_id
    assert dispatched_prompts == []

    ready_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{second_upstream_id}",
        params={"project_path": PROJECT_PATH},
        json={"status": "AWAITING_REVIEW"},
    )

    assert ready_response.status_code == 200
    second_upstream = ready_response.json()
    assert second_upstream["dependents"][0]["id"] == downstream_id
    await asyncio.wait_for(prompt_started.wait(), timeout=PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS)
    assert len(dispatched_prompts) == 1
    assert "Wire UI" in dispatched_prompts[0]["prompt"]
    downstream_before_prompt_done = await _wait_for_project_todo_stage(
        db_client,
        downstream_id,
        "TERMINAL_READY",
    )
    assert downstream_before_prompt_done.status == ProjectTodoStatus.todo
    assert downstream_before_prompt_done.assigned_window_id is not None
    assert dispatched_prompts[0]["window_id"] == str(downstream_before_prompt_done.assigned_window_id)

    allow_prompt_finish.set()
    await _wait_for_project_todo_status(db_client, downstream_id, ProjectTodoStatus.dispatched)

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    todos = {todo["id"]: todo for todo in list_response.json()["todos"]}
    downstream = todos[downstream_id]
    assert downstream["status"] == "DISPATCHED"
    assert downstream["queued_dispatch"] is False
    assert downstream["dispatch_stage"] is None
    assert downstream["dispatch_error"] is None
    assert downstream["assigned_window_id"] == dispatched_prompts[0]["window_id"]
    downstream_detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{downstream_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert downstream_detail_response.status_code == 200
    downstream_detail = downstream_detail_response.json()
    assert {dependency["id"] for dependency in downstream_detail["dependencies"]} == {
        first_upstream_id,
        second_upstream_id,
    }
    window = await wait_for_local_window_ready(db_client, client_id, downstream["assigned_window_id"])
    assert window.cwd == PROJECT_PATH
    assert window.shell_command == "codex"
