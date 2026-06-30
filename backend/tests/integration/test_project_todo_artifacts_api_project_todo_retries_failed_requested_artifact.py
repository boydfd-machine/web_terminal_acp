from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

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
async def test_project_todo_retries_failed_requested_artifact(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todo_artifact_cards_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Retry artifact",
            "artifact_kinds": ["agent_trace_graph"],
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
                title="Todo implementation",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="agent_trace_graph",
            title="Retry artifact - Agent Trace Graph",
            metadata_json={"purpose": "todo_artifact"},
        )
        await mark_artifact_failed(session, artifact, error="artifact generation timed out")
        link = ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=window_id,
            purpose="todo_artifact",
        )
        session.add(link)
        await session.commit()
        link_id = link.id
        artifact_id = artifact.id

    retry_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/artifacts/{link_id}/retry",
        params={"project_path": PROJECT_PATH},
    )

    assert retry_response.status_code == 200
    linked = retry_response.json()["artifacts"][0]
    assert linked["id"] == str(link_id)
    assert linked["artifact_id"] == str(artifact_id)
    assert linked["status"] == "PENDING"
    assert linked["last_error"] is None
    assert linked["metadata_json"]["project_todo_id"] == todo_id
    assert linked["metadata_json"]["purpose"] == "todo_artifact"
    assert linked["metadata_json"]["dispatch_attempted_at"]
    assert len(scheduled) == 1
    assert scheduled[0].artifact_id == artifact_id
    assert scheduled[0].window_id == window_id

@pytest.mark.asyncio
async def test_artifact_card_creation_sets_source_todo_as_parent(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review original requirement"},
    )
    other_parent_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Do not use this parent"},
    )
    assert source_response.status_code == 200
    assert other_parent_response.status_code == 200
    source_todo_id = source_response.json()["id"]
    other_parent_id = other_parent_response.json()["id"]

    window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Requirement review terminal",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="requirement_review_report",
            title="Requirement review",
        )
        await mark_artifact_succeeded(
            session,
            artifact,
            content_json={"artifact_kind": "requirement_review_report", "executive_summary": "Review"},
            display_html="<button>Add to board</button>",
            metadata_json={"renderer": "requirement-review-report"},
        )
        session.add(
            ProjectTodoArtifact(
                project_todo_id=UUID(source_todo_id),
                terminal_artifact_id=artifact.id,
                created_by_window_id=window_id,
                purpose="todo_artifact",
            )
        )
        await session.commit()
        artifact_id = artifact.id

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/from-artifact-card",
        params={"project_path": PROJECT_PATH},
        json={
            "artifact_id": str(artifact_id),
            "card": {
                "title": "Implement optimized requirement",
                "description": "Created from the requirement review report.",
                "parent_todo_id": other_parent_id,
                "todo_type_id": "default",
                "artifact_kinds": ["agent_trace_graph"],
            },
        },
    )

    assert create_response.status_code == 200, create_response.json()
    created = create_response.json()
    assert created["title"] == "Implement optimized requirement"
    assert created["parent_todo_id"] == source_todo_id
    assert created["parent_todo"]["title"] == "Review original requirement"
    assert created["todo_type_id"] == "default"
    assert created["artifact_kinds"] == ["agent_trace_graph"]
    assert created["artifacts"][0]["artifact_id"] == str(artifact_id)
    assert created["artifacts"][0]["purpose"] == "artifact_card"

@pytest.mark.asyncio
async def test_project_todo_retry_rejects_succeeded_requested_artifact(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todo_artifact_cards_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Do not retry success",
            "artifact_kinds": ["agent_trace_graph"],
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
                title="Todo implementation",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="agent_trace_graph",
            title="Do not retry success - Agent Trace Graph",
            metadata_json={"purpose": "todo_artifact"},
        )
        artifact.status = TerminalArtifactStatus.succeeded
        link = ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=window_id,
            purpose="todo_artifact",
        )
        session.add(link)
        await session.commit()
        link_id = link.id

    retry_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/artifacts/{link_id}/retry",
        params={"project_path": PROJECT_PATH},
    )

    assert retry_response.status_code == 409
    assert retry_response.json()["detail"] == "artifact is not failed"
    assert scheduled == []

@pytest.mark.asyncio
async def test_project_todo_requested_artifacts_wait_for_remote_client_connection(
    db_client,
    monkeypatch,
) -> None:
    remote_client_id = await create_remote_client_id(db_client, name="remote-artifact-client")
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
            "title": "Generate remote research artifact",
            "artifact_kinds": ["agent_trace_graph"],
        },
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()

    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(remote_client_id),
                title="Remote todo implementation",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        first_old_artifact = await create_terminal_artifact(
            session,
            client_id=UUID(remote_client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="agent_trace_graph",
            title="Old failed trace artifact",
            metadata_json={"purpose": "todo_artifact"},
        )
        await mark_artifact_failed(
            session,
            first_old_artifact,
            error=f"remote client unavailable: {remote_client_id}",
        )
        second_old_artifact = await create_terminal_artifact(
            session,
            client_id=UUID(remote_client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="agent_trace_graph",
            title="Duplicate failed trace artifact",
            metadata_json={"purpose": "todo_artifact"},
        )
        await mark_artifact_failed(
            session,
            second_old_artifact,
            error=f"remote client unavailable: {remote_client_id}",
        )
        session.add(
            ProjectTodoArtifact(
                project_todo_id=todo.id,
                terminal_artifact_id=first_old_artifact.id,
                created_by_window_id=window_id,
                purpose="todo_artifact",
            )
        )
        session.add(
            ProjectTodoArtifact(
                project_todo_id=todo.id,
                terminal_artifact_id=second_old_artifact.id,
                created_by_window_id=window_id,
                purpose="todo_artifact",
            )
        )
        await session.commit()

    unavailable_response = await db_client.get(
        f"/api/clients/{remote_client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert unavailable_response.status_code == 200
    assert scheduled == []
    async with db_client.session_factory() as session:
        artifact_ids = list(
            await session.scalars(
                select(TerminalArtifact.id)
                .join(ProjectTodoArtifact, ProjectTodoArtifact.terminal_artifact_id == TerminalArtifact.id)
                .where(ProjectTodoArtifact.project_todo_id == UUID(todo_id))
            )
        )
    assert set(artifact_ids) == {first_old_artifact.id, second_old_artifact.id}

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
        assert scheduled[0].window_id == window_id
        assert scheduled[0].artifact_id in {first_old_artifact.id, second_old_artifact.id}
        async with db_client.session_factory() as session:
            rows = list(
                await session.execute(
                    select(ProjectTodoArtifact, TerminalArtifact)
                    .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
                    .where(ProjectTodoArtifact.project_todo_id == UUID(todo_id))
                )
            )
        assert len(rows) == 2
        artifact_by_id = {artifact.id: (link, artifact) for link, artifact in rows}
        retried_link, retried_artifact = artifact_by_id[scheduled[0].artifact_id]
        assert retried_link.terminal_artifact_id == scheduled[0].artifact_id
        assert retried_artifact.status.value == "PENDING"
        assert retried_artifact.last_error is None
        assert retried_artifact.artifact_kind == "agent_trace_graph"
        failed_artifacts = [
            artifact
            for artifact_id, (_link, artifact) in artifact_by_id.items()
            if artifact_id != scheduled[0].artifact_id
        ]
        assert len(failed_artifacts) == 1
        assert failed_artifacts[0].status.value == "FAILED"
    finally:
        await registry.unregister(UUID(remote_client_id))
