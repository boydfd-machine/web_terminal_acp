from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.config import get_settings
from app.models import ProjectTodo, ProjectTodoRun, ProjectTodoStatus, VirtualWindow
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-todos-periodic"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_todo_periodic_schedule_fields_round_trip(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    invalid_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Invalid schedule",
            "trigger_strategy": "CRON",
            "cron_expression": "0 9 * * 1",
        },
    )
    assert invalid_response.status_code == 400
    assert "cron trigger requires a periodic todo" in invalid_response.json()["detail"]

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Weekly cleanup",
            "description": "Remove stale branches",
            "execution_kind": "PERIODIC",
            "terminal_policy": "REUSE_LATEST",
            "trigger_strategy": "CRON",
            "cron_expression": "0 9 * * 1",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["execution_kind"] == "PERIODIC"
    assert created["terminal_policy"] == "REUSE_LATEST"
    assert created["trigger_strategy"] == "CRON"
    assert created["cron_expression"] == "0 9 * * 1"
    assert created["schedule_enabled"] is True
    assert created["next_trigger_at"] is not None
    assert created["execution_run_count"] == 0
    assert created["execution_runs"] == []

    disabled_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
        json={"schedule_enabled": False},
    )
    assert disabled_response.status_code == 200
    disabled = disabled_response.json()
    assert disabled["execution_kind"] == "PERIODIC"
    assert disabled["terminal_policy"] == "REUSE_LATEST"
    assert disabled["trigger_strategy"] == "CRON"
    assert disabled["cron_expression"] == "0 9 * * 1"
    assert disabled["schedule_enabled"] is False
    assert disabled["next_trigger_at"] is None

    enabled_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
        json={"schedule_enabled": True},
    )
    assert enabled_response.status_code == 200
    enabled = enabled_response.json()
    assert enabled["trigger_strategy"] == "CRON"
    assert enabled["cron_expression"] == "0 9 * * 1"
    assert enabled["schedule_enabled"] is True
    assert enabled["next_trigger_at"] is not None

    manual_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
        json={"trigger_strategy": "MANUAL"},
    )
    assert manual_response.status_code == 200
    manual = manual_response.json()
    assert manual["execution_kind"] == "PERIODIC"
    assert manual["trigger_strategy"] == "MANUAL"
    assert manual["cron_expression"] is None
    assert manual["schedule_enabled"] is False
    assert manual["next_trigger_at"] is None


@pytest.mark.asyncio
async def test_periodic_project_todo_returns_to_todo_after_execution(db_client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", False)
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Periodic smoke", "execution_kind": "PERIODIC"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    dispatched_at = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    completed_at = dispatched_at + timedelta(minutes=2)
    async with db_client.session_factory() as session:
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Periodic terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        window.agent_activity_latest_completed_at = completed_at
        session.add(window)
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.dispatch_prompt = "Run periodic smoke"
        todo.dispatched_at = dispatched_at
        todo.execution_run_count = 1
        session.add(
            ProjectTodoRun(
                project_todo_id=todo.id,
                client_id=UUID(client_id),
                project_path=PROJECT_PATH,
                window_id=window_id,
                run_number=1,
                trigger_strategy="MANUAL",
                trigger_reason="manual",
                terminal_policy="NEW_TERMINAL",
                dispatch_mode="submit",
                prompt="Run periodic smoke",
                status="DISPATCHED",
                started_at=dispatched_at,
                dispatched_at=dispatched_at,
            )
        )
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [todo] = list_response.json()["todos"]
    assert todo["status"] == "TODO"
    assert todo["assigned_window_id"] == str(window_id)
    assert todo["execution_kind"] == "PERIODIC"
    assert todo["execution_run_count"] == 1
    assert todo["review_status"] == "NOT_REQUESTED"
    assert todo["awaiting_review_at"] is None
    assert len(todo["execution_runs"]) == 1
    [run] = todo["execution_runs"]
    assert run["run_number"] == 1
    assert run["status"] == "COMPLETED"
    assert run["window_id"] == str(window_id)
    assert run["prompt"] == "Run periodic smoke"
    assert run["completed_at"] is not None
    assert run["assigned_terminal"]["title"] == "Periodic terminal"
