from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.contexts.workspace.application import project_todo_review_dispatch as review_dispatch_service
from app.models import ProjectTodo, ProjectTodoStatus
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-todos"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_review_config_round_trip(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    read_response = await db_client.get(
        f"/api/clients/{client_id}/projects/review-config",
        params={"project_path": PROJECT_PATH},
    )

    assert read_response.status_code == 200
    initial = read_response.json()
    assert initial["project_path"] == PROJECT_PATH
    assert initial["pr_provider"] == "LOCAL_CARD"
    assert initial["review_agent_profile_id"] == "builtin/developer"
    assert initial["auto_create_review_target"] is True
    assert initial["auto_dispatch_review"] is False
    assert initial["merge_policy"] == "MANUAL"

    update_response = await db_client._client.put(
        f"/api/clients/{client_id}/projects/review-config",
        params={"project_path": PROJECT_PATH},
        json={
            "pr_provider": "LOCAL_CARD",
            "pr_provider_config": {"base_branch": "main"},
            "review_agent": "codex",
            "review_agent_command": "codex",
            "review_agent_profile_id": "builtin/developer",
            "auto_create_review_target": True,
            "auto_dispatch_review": True,
            "merge_policy": "AUTO_AFTER_PASSED",
            "required_artifact_kinds": ["review_report", "test_report"],
        },
    )

    assert update_response.status_code == 200
    saved = update_response.json()
    assert saved["pr_provider_config"] == {"base_branch": "main"}
    assert saved["review_agent"] == "codex"
    assert saved["review_agent_command"] == "codex"
    assert saved["review_agent_profile_id"] == "builtin/developer"
    assert saved["auto_dispatch_review"] is True
    assert saved["merge_policy"] == "AUTO_AFTER_PASSED"
    assert saved["required_artifact_kinds"] == ["review_report", "test_report"]


@pytest.mark.asyncio
async def test_project_todo_auto_review_dispatches_configured_pending_card(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review me"},
    )
    todo_id = create_response.json()["id"]
    await db_client._client.put(
        f"/api/clients/{client_id}/projects/review-config",
        params={"project_path": PROJECT_PATH},
        json={
            "pr_provider": "LOCAL_CARD",
            "review_agent": "codex",
            "review_agent_command": "codex",
            "review_agent_profile_id": "builtin/developer",
            "auto_create_review_target": True,
            "auto_dispatch_review": True,
            "merge_policy": "MANUAL",
            "required_artifact_kinds": [],
        },
    )
    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.review_status = "PENDING"
        todo.awaiting_review_at = datetime.now(timezone.utc)
        await session.commit()

    launched: list[tuple[str, str, str | None]] = []

    async def fake_dispatch_project_todo_review_window(**kwargs):
        target = kwargs["todo"]
        launch = kwargs["agent_launch"]
        launched.append((str(target.id), launch.agent, launch.profile_id))
        target.review_status = "RUNNING"
        await kwargs["session"].commit()
        return target

    monkeypatch.setattr(
        review_dispatch_service,
        "dispatch_project_todo_review_window",
        fake_dispatch_project_todo_review_window,
    )

    processed = await review_dispatch_service.process_project_todo_auto_reviews_once(
        db_client.session_factory,
        tmux_manager=object(),
        registry=None,
        ui_event_hub=object(),
    )

    assert processed == 1
    assert launched == [(todo_id, "codex", "builtin/developer")]
    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        assert todo.review_status == "RUNNING"
