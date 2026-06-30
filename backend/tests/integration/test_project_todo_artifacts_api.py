from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pathlib import Path
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
from app.platform.plugins.artifact_plugins.management import (
    save_artifact_plugin_components,
)
from app.platform.plugins.artifact_plugins.registry import reset_artifact_plugin_registries
from tests.integration.test_window_api_support import create_remote_client_id, get_local_client_id

PROJECT_PATH = "/tmp/project-todo-artifacts"
pytest_plugins = ["tests.integration.test_window_api_support"]

@pytest.mark.asyncio
async def test_project_todo_links_terminal_artifacts(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review artifacts"},
    )
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    async with db_client.session_factory() as session:
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Review terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add(window)
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_kind="agent_trace_graph",
            title="Review trace",
        )
        artifact_id = artifact.id
        await session.commit()

    link_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/artifacts",
        params={"project_path": PROJECT_PATH},
        json={"artifact_id": str(artifact_id), "purpose": "review-test"},
    )

    assert link_response.status_code == 200
    linked = link_response.json()
    assert linked["artifacts"] == [
        {
            "id": linked["artifacts"][0]["id"],
            "artifact_id": str(artifact_id),
            "client_id": client_id,
            "window_id": str(window_id),
            "source_window_id": str(window_id),
            "ephemeral_window_id": None,
            "review_run_id": None,
            "created_by_window_id": str(window_id),
            "artifact_scope": "terminal",
            "project_path": None,
            "title": "Review trace",
            "artifact_kind": "agent_trace_graph",
            "status": "PENDING",
            "purpose": "review-test",
            "agent_name": None,
            "agent_status": None,
            "metadata_json": None,
            "last_error": None,
            "started_at": None,
            "completed_at": None,
            "created_at": linked["artifacts"][0]["created_at"],
            "updated_at": linked["artifacts"][0]["updated_at"],
        }
    ]

@pytest.mark.asyncio
async def test_project_todo_requested_artifacts_are_created_when_todo_is_ready(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Generate implementation trace",
            "artifact_kinds": ["agent_trace_graph", " agent_trace_graph "],
        },
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    assert create_response.json()["artifact_kinds"] == ["agent_trace_graph"]

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
        await session.commit()

    first_list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert first_list_response.status_code == 200
    [listed] = first_list_response.json()["todos"]
    assert listed["artifact_kinds"] == ["agent_trace_graph"]
    first_detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert first_detail_response.status_code == 200
    assert len(first_detail_response.json()["artifacts"]) == 1
    linked = first_detail_response.json()["artifacts"][0]
    assert linked["artifact_kind"] == "agent_trace_graph"
    assert linked["artifact_scope"] == "terminal"
    assert linked["project_path"] is None
    assert linked["purpose"] == "todo_artifact"
    assert linked["status"] == "PENDING"
    assert linked["window_id"] == str(window_id)
    assert linked["source_window_id"] == str(window_id)
    assert linked["metadata_json"]["project_todo_id"] == todo_id
    assert linked["metadata_json"]["purpose"] == "todo_artifact"
    assert len(scheduled) == 1
    assert str(scheduled[0].client_id) == client_id
    assert scheduled[0].window_id == window_id
    assert str(scheduled[0].artifact_id) == linked["artifact_id"]
    assert scheduled[0].output_language == "中文"

    second_list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert second_list_response.status_code == 200
    second_detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert second_detail_response.status_code == 200
    assert len(second_detail_response.json()["artifacts"]) == 1
    assert len(scheduled) == 1
    async with db_client.session_factory() as session:
        rows = list(
            await session.execute(
                select(ProjectTodoArtifact, TerminalArtifact)
                .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
                .where(ProjectTodoArtifact.project_todo_id == UUID(todo_id))
            )
        )
    assert len(rows) == 1
    link, artifact = rows[0]
    assert link.purpose == "todo_artifact"
    assert artifact.artifact_kind == "agent_trace_graph"
    assert artifact.artifact_scope == "terminal"
    assert artifact.project_path is None


@pytest.mark.asyncio
async def test_requested_artifact_carries_project_todo_artifact_model_selection(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Artifact model todo",
            "artifact_kinds": ["agent_trace_graph"],
            "artifact_model_selection": {
                "preset_id": "openai-artifacts",
                "model": "gpt-5-mini",
                "codex_model_reasoning_effort": "high",
            },
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
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    assert len(scheduled) == 1
    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    linked = detail_response.json()["artifacts"][0]
    assert linked["metadata_json"]["artifact_model_selection"] == {
        "preset_id": "openai-artifacts",
        "model": "gpt-5-mini",
        "codex_model_reasoning_effort": "high",
    }

@pytest.mark.asyncio
async def test_project_todo_list_artifact_creation_uses_candidates_outside_date_filter(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    old_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Old ready artifact todo",
            "artifact_kinds": ["agent_trace_graph"],
        },
    )
    recent_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Recent visible todo"},
    )
    assert old_response.status_code == 200
    assert recent_response.status_code == 200
    old_todo_id = old_response.json()["id"]
    recent_todo_id = recent_response.json()["id"]
    window_id = uuid4()
    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Old implementation",
                cwd=PROJECT_PATH,
                shell_command="codex",
            )
        )
        old_todo = await session.get(ProjectTodo, UUID(old_todo_id))
        recent_todo = await session.get(ProjectTodo, UUID(recent_todo_id))
        assert old_todo is not None
        assert recent_todo is not None
        old_todo.status = ProjectTodoStatus.awaiting_review
        old_todo.assigned_window_id = window_id
        old_todo.updated_at = datetime.now(UTC) - timedelta(days=3)
        recent_todo.updated_at = datetime.now(UTC)
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH, "range": "1d"},
    )

    assert list_response.status_code == 200
    assert [todo["id"] for todo in list_response.json()["todos"]] == [recent_todo_id]
    assert len(scheduled) == 1
    assert scheduled[0].window_id == window_id
    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{old_todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert detail_response.status_code == 200
    assert len(detail_response.json()["artifacts"]) == 1

@pytest.mark.asyncio
async def test_project_todo_list_does_not_create_artifacts_before_implementation_finishes(
    db_client,
    monkeypatch,
) -> None:
    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Wait for implementation",
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
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = window_id
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["status"] == "DISPATCHED"
    assert listed["artifacts"] == []
    assert scheduled == []

@pytest.mark.asyncio
async def test_project_todo_requested_project_artifacts_are_created_when_todo_is_ready(
    db_client,
    monkeypatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    reset_artifact_plugin_registries()
    save_artifact_plugin_components(
        "project",
        python_source='''
ARTIFACT_KIND = "demo_project_artifact"
LABEL = "Demo Project Artifact"
DEFAULT_TITLE = "Demo project artifact"


def normalize_content(content):
    return {**content, "normalized": True}


def metadata_json(content):
    return {
        "renderer": "demo-project-artifact",
        "artifact_kind": "demo_project_artifact",
        "artifact_scope": "project",
        "project_path": "/tmp/project-todo-artifacts",
    }
'''.strip(),
        prompt_template="Build {{ artifact_kind }} for {{ source_title }}. {{ output_instruction }}",
        html_template="<html><body><h1>{{ content.title }}</h1></body></html>",
        json_schema={
            "type": "object",
            "required": ["artifact_kind", "title"],
            "properties": {
                "artifact_kind": {"const": "demo_project_artifact"},
                "title": {"type": "string"},
                "normalized": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        preview_content_json={
            "artifact_kind": "demo_project_artifact",
            "title": "Demo project artifact preview",
        },
        allow_overwrite=True,
        home=home,
    )

    client_id = await get_local_client_id(db_client)
    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime) -> None:
        scheduled.extend(generations)

    monkeypatch.setattr(
        project_todos_routes,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Generate user journey",
            "artifact_kinds": ["project:demo_project_artifact", " project:demo_project_artifact "],
        },
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    assert create_response.json()["artifact_kinds"] == ["project:demo_project_artifact"]

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
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )

    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["artifact_kinds"] == ["project:demo_project_artifact"]
    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert detail_response.status_code == 200
    assert len(detail_response.json()["artifacts"]) == 1
    linked = detail_response.json()["artifacts"][0]
    assert linked["artifact_kind"] == "demo_project_artifact"
    assert linked["artifact_scope"] == "project"
    assert linked["project_path"] == PROJECT_PATH
    assert linked["metadata_json"]["artifact_scope"] == "project"
    assert linked["metadata_json"]["project_path"] == PROJECT_PATH
    assert len(scheduled) == 1
    assert scheduled[0].window_id == window_id

    project_artifacts_response = await db_client.get(
        f"/api/clients/{client_id}/projects/artifacts",
        params={"project_path": PROJECT_PATH},
    )
    assert project_artifacts_response.status_code == 200
    [project_artifact] = project_artifacts_response.json()["artifacts"]
    assert project_artifact["id"] == linked["artifact_id"]
    assert project_artifact["artifact_scope"] == "project"
    assert project_artifact["project_path"] == PROJECT_PATH
