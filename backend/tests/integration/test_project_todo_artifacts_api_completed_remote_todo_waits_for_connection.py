from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.workspace.api import project_todo_artifact_cards_routes, project_todos_routes
from app.models import (
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoStatus,
    TerminalArtifact,
    TerminalArtifactStatus,
    VirtualWindow,
)
from app.main import app
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_failed, mark_artifact_succeeded
from tests.integration.test_window_api_support import create_remote_client_id, get_local_client_id

PROJECT_PATH = "/tmp/project-todo-artifacts"
pytest_plugins = ["tests.integration.test_window_api_support"]

@pytest.mark.asyncio
async def test_completed_remote_todo_waits_for_connection_before_requested_artifact(
    db_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", False)
    remote_client_id = await create_remote_client_id(db_client, name="remote-completed-artifact-client")
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Generate after completion",
            "artifact_kinds": ["agent_trace_graph"],
        },
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    dispatched_at = datetime(2026, 6, 7, 8, 0, tzinfo=UTC)
    completed_at = datetime(2026, 6, 7, 8, 5, tzinfo=UTC)

    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(remote_client_id),
                title="Remote completed todo",
                cwd=PROJECT_PATH,
                shell_command="codex",
                agent_activity_latest_completed_at=completed_at,
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = window_id
        todo.dispatched_at = dispatched_at
        await session.commit()

    unavailable_response = await db_client.get(
        f"/api/clients/{remote_client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert unavailable_response.status_code == 200
    assert scheduled == []
    async with db_client.session_factory() as session:
        stored_todo = await session.get(ProjectTodo, UUID(todo_id))
        assert stored_todo is not None
        assert stored_todo.status == ProjectTodoStatus.dispatched
        artifact_count = len(
            list(
                await session.scalars(
                    select(TerminalArtifact.id)
                    .join(ProjectTodoArtifact, ProjectTodoArtifact.terminal_artifact_id == TerminalArtifact.id)
                    .where(ProjectTodoArtifact.project_todo_id == UUID(todo_id))
                )
            )
        )
    assert artifact_count == 0

    registry = client_connection_registry_from_state(app.state)
    open_connection = type("OpenRemoteConnection", (), {"closed": False})()
    await registry.register(UUID(remote_client_id), open_connection)
    try:
        available_response = await db_client.get(
            f"/api/clients/{remote_client_id}/projects/todos",
            params={"project_path": PROJECT_PATH},
        )

        assert available_response.status_code == 200
        assert len(scheduled) == 1
        async with db_client.session_factory() as session:
            stored_todo = await session.get(ProjectTodo, UUID(todo_id))
            assert stored_todo is not None
            assert stored_todo.status == ProjectTodoStatus.dispatched
            [artifact] = list(
                await session.scalars(
                    select(TerminalArtifact)
                    .join(ProjectTodoArtifact, ProjectTodoArtifact.terminal_artifact_id == TerminalArtifact.id)
                    .where(ProjectTodoArtifact.project_todo_id == UUID(todo_id))
                )
            )
        assert artifact.status.value == "PENDING"
        assert scheduled[0].artifact_id == artifact.id
    finally:
        await registry.unregister(UUID(remote_client_id))

@pytest.mark.asyncio
async def test_project_todo_requested_artifact_edits_are_locked_after_todo_status(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Lock requested artifact edits"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]

    editable_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"artifact_kinds": ["agent_trace_graph"]},
    )
    assert editable_response.status_code == 200
    assert editable_response.json()["artifact_kinds"] == ["agent_trace_graph"]

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        await session.commit()

    locked_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"artifact_kinds": []},
    )
    assert locked_response.status_code == 409
    assert locked_response.json()["detail"] == "artifact selection is locked"

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        assert todo.artifact_kinds_json == ["agent_trace_graph"]

@pytest.mark.asyncio
async def test_project_todo_rejects_unknown_requested_artifact_kind(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Invalid artifact",
            "artifact_kinds": ["not_a_real_artifact"],
        },
    )

    assert response.status_code == 400
    assert "unsupported terminal artifact kind" in response.json()["detail"]
