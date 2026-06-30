import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.models import (
    Event,
    EventSourceType,
    GitWorktreeRun,
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoStatus,
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
async def test_project_todo_crud_and_clear_description(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Document dependency",
            "description": "Blocked by API migration",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["project_path"] == PROJECT_PATH
    assert created["status"] == "TODO"
    assert created["description"] == "Blocked by API migration"
    assert created["review_strategy"] == "LOCAL_CARD"
    assert created["review_status"] == "NOT_REQUESTED"
    assert created["review_unseen"] is False
    assert created["needs_human_review"] is False
    assert created["todo_type"]["id"] == "default"
    assert created["todo_type"]["scope"] == "system"
    assert created["todo_type"]["agent"] is None
    assert created["artifacts"] == []
    assert created["artifact_model_selection"] is None
    assert created["dependencies"] == []
    assert created["dependents"] == []
    assert created["referenced_todos"] == []
    assert created["queued_dispatch"] is False

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
        json={
            "description": None,
            "status": "BLOCKED",
            "review_status": "NEEDS_HUMAN_REVIEW",
            "review_notes": "Security-sensitive change",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["description"] is None
    assert patched["status"] == "BLOCKED"
    assert patched["review_status"] == "NEEDS_HUMAN_REVIEW"
    assert patched["needs_human_review"] is True
    assert patched["review_notes"] == "Security-sensitive change"

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["id"] == created["id"]
    assert "description" not in listed
    assert "dispatch_prompt" not in listed
    assert "review_prompt" not in listed
    assert "review_notes" not in listed
    assert "execution_runs" not in listed
    assert listed["artifacts"] == []
    assert "referenced_todos" not in listed

    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == created["id"]
    assert detail["description"] is None
    assert detail["review_notes"] == "Security-sensitive change"
    assert detail["artifacts"] == []
    assert detail["execution_runs"] == []

    delete_response = await db_client.delete(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_project_todo_persists_artifact_model_selection(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Artifact model override",
            "artifact_model_selection": {
                "preset_id": "openai-artifacts",
                "model": "gpt-5-mini",
                "codex_model_reasoning_effort": "high",
            },
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["artifact_model_selection"] == {
        "preset_id": "openai-artifacts",
        "model": "gpt-5-mini",
        "codex_model_reasoning_effort": "high",
    }

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["artifact_model_selection"] == created["artifact_model_selection"]

@pytest.mark.asyncio
async def test_project_todo_list_filters_by_updated_at_query_params(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    custom_day = (now - timedelta(days=3)).date()
    created_ids: list[str] = []
    for title in ["Recent card", "Custom window card", "Old card"]:
        response = await db_client.post(
            f"/api/clients/{client_id}/projects/todos",
            params={"project_path": PROJECT_PATH},
            json={"title": title},
        )
        assert response.status_code == 200
        created_ids.append(response.json()["id"])

    async with db_client.session_factory() as session:
        recent = await session.get(ProjectTodo, UUID(created_ids[0]))
        custom = await session.get(ProjectTodo, UUID(created_ids[1]))
        old = await session.get(ProjectTodo, UUID(created_ids[2]))
        assert recent is not None
        assert custom is not None
        assert old is not None
        recent.updated_at = now - timedelta(days=1)
        custom.updated_at = datetime.combine(custom_day, datetime.max.time(), tzinfo=timezone.utc)
        old.updated_at = now - timedelta(days=40)
        await session.commit()

    range_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH, "range": "30d"},
    )
    assert range_response.status_code == 200
    assert {todo["title"] for todo in range_response.json()["todos"]} == {"Recent card", "Custom window card"}

    custom_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={
            "project_path": PROJECT_PATH,
            "range": "custom",
            "start_date": custom_day.isoformat(),
            "end_date": custom_day.isoformat(),
        },
    )
    assert custom_response.status_code == 200
    assert [todo["title"] for todo in custom_response.json()["todos"]] == ["Custom window card"]

    invalid_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={
            "project_path": PROJECT_PATH,
            "range": "custom",
            "start_date": "2026-06-04",
            "end_date": "2026-06-03",
        },
    )
    assert invalid_response.status_code == 422

@pytest.mark.asyncio
async def test_project_todo_list_uses_lightweight_assigned_terminal_projection(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Terminal metadata only"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Assigned terminal",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.assigned_window_id = window_id
        await session.commit()

    def fail_if_heavy_activity_projection_runs(*args, **kwargs):
        raise AssertionError("todo list should not load heavy terminal activity projection")

    monkeypatch.setattr(
        "app.contexts.windows.application.assigned_terminal_summary.load_tree_window_activity",
        fail_if_heavy_activity_projection_runs,
    )

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["assigned_terminal"]["id"] == str(window_id)
    assert listed["assigned_terminal"]["title"] == "Assigned terminal"
    assert listed["assigned_terminal"]["work_status"]["state"] == "LONG_IDLE"

@pytest.mark.asyncio
async def test_create_project_todo_can_select_parent_card(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    parent_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Parent feature"},
    )
    assert parent_response.status_code == 200
    parent = parent_response.json()

    child_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Child task",
            "description": "Implement the first slice.",
            "parent_todo_id": parent["id"],
        },
    )
    assert child_response.status_code == 200
    child = child_response.json()
    assert child["parent_todo_id"] == parent["id"]
    assert child["parent_todo"] == {
        "id": parent["id"],
        "title": "Parent feature",
        "status": "TODO",
        "completed_at": None,
    }

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    listed = {todo["title"]: todo for todo in list_response.json()["todos"]}
    assert listed["Child task"]["parent_todo_id"] == parent["id"]
    assert listed["Child task"]["parent_todo"]["title"] == "Parent feature"
    assert listed["Parent feature"]["child_todos"] == [
        {
            "id": child["id"],
            "title": "Child task",
            "status": "TODO",
            "completed_at": None,
        }
    ]
    assert listed["Child task"]["child_todos"] == []

    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{child['id']}",
        params={"project_path": PROJECT_PATH},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["parent_todo"]["id"] == parent["id"]
    assert detail_response.json()["child_todos"] == []

    parent_detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{parent['id']}",
        params={"project_path": PROJECT_PATH},
    )
    assert parent_detail_response.status_code == 200
    assert parent_detail_response.json()["child_todos"][0]["id"] == child["id"]

@pytest.mark.asyncio
async def test_create_project_todo_rejects_parent_from_another_project(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    parent_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": "/tmp/project-todos-parent-other"},
        json={"title": "Other project parent"},
    )
    assert parent_response.status_code == 200

    child_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Invalid child",
            "parent_todo_id": parent_response.json()["id"],
        },
    )

    assert child_response.status_code == 400
    assert child_response.json()["detail"] == "parent todo not found"

@pytest.mark.asyncio
async def test_project_todo_annotation_appends_without_dispatch(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Polish selected UI",
            "description": "Existing implementation context.",
        },
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Todo worker",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.awaiting_review_at = datetime.now(timezone.utc)
        todo.review_status = "PENDING"
        await session.commit()

    append_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/annotations",
        params={"project_path": PROJECT_PATH},
        json={
            "annotation": (
                "Source: Debug page annotation\n"
                "Route: /clients/client-1/terminals/window-1\n"
                "Selection: x=12, y=24, width=180, height=96\n\n"
                "Requested change:\nMake this panel easier to scan."
            )
        },
    )

    assert append_response.status_code == 200
    annotated = append_response.json()
    assert annotated["status"] == "AWAITING_REVIEW"
    assert annotated["assigned_window_id"] == str(window_id)
    assert annotated["review_status"] == "PENDING"
    assert annotated["dispatch_stage"] is None
    assert annotated["description"].startswith("Existing implementation context.")
    assert "Debug page annotation" in annotated["description"]
    assert "Route: /clients/client-1/terminals/window-1" in annotated["description"]
    assert "Requested change:\nMake this panel easier to scan." in annotated["description"]
    async with db_client.session_factory() as session:
        stored = await session.get(ProjectTodo, UUID(todo_id))
    assert stored is not None
    assert stored.status == ProjectTodoStatus.awaiting_review
    assert stored.assigned_window_id == window_id
    assert stored.dispatch_stage is None
