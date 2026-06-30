from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.contexts.workspace.application import project_todo_review_dispatch as review_dispatch_service
from app.models import ProjectTodo, ProjectTodoStatus, VirtualWindow
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-todos"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_todo_review_dispatch_creates_run_and_manual_verdict(
    db_client,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    scheduled: list[dict[str, object]] = []

    def fake_schedule_project_todo_prompt_dispatch(**kwargs) -> None:
        scheduled.append({"window_id": str(kwargs["window_id"]), "prompt": kwargs["prompt"]})

    monkeypatch.setattr(
        review_dispatch_service,
        "schedule_project_todo_prompt_dispatch",
        fake_schedule_project_todo_prompt_dispatch,
    )
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review dispatch run"},
    )
    todo_id = create_response.json()["id"]
    implementation_window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=implementation_window_id,
                client_id=UUID(client_id),
                title="Implementation terminal",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.review_status = "PENDING"
        todo.assigned_window_id = implementation_window_id
        todo.implementation_worktree_json = {
            "worktree_root": "/tmp/project-todos/.worktrees/review-dispatch",
            "branch": "agent/review-dispatch",
            "start_head": "base",
            "end_head": "feature",
            "commits": [{"sha": "feature"}],
            "files": [{"path": "frontend/app.tsx", "status": "modified"}],
        }
        todo.awaiting_review_at = datetime.now(timezone.utc)
        await session.commit()

    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/review/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": "builtin/developer",
            },
        },
    )
    assert dispatch_response.status_code == 200
    dispatched = dispatch_response.json()
    assert dispatched["review_status"] == "RUNNING"
    assert dispatched["review_window_id"] == scheduled[0]["window_id"]
    assert "Review dispatch run" in scheduled[0]["prompt"]
    home = tmp_path / ".web-terminal-acp" / "codex-homes" / dispatched["review_window_id"]
    assert (home / "AGENTS.md").is_file()
    assert (home / "skills" / "tdd" / "SKILL.md").is_file()

    runs_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/review-runs",
        params={"project_path": PROJECT_PATH},
    )
    assert runs_response.status_code == 200
    [run] = runs_response.json()["review_runs"]
    assert run["review_window_id"] == dispatched["review_window_id"]
    assert run["agent_client"] == "codex"
    assert run["agent_profile_id"] == "builtin/developer"
    assert run["status"] == "RUNNING"

    approve_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"review_status": "APPROVED"},
    )
    assert approve_response.status_code == 200
    approved_runs_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/review-runs",
        params={"project_path": PROJECT_PATH},
    )
    [approved_run] = approved_runs_response.json()["review_runs"]
    assert approved_run["status"] == "PASSED"
    assert approved_run["completed_at"] is not None
