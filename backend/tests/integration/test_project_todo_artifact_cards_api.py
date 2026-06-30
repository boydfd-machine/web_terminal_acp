from uuid import UUID, uuid4

import pytest
from pathlib import Path

from app.models import ProjectTodoArtifact, VirtualWindow
from app.platform.plugins.artifact_plugins.management import save_artifact_plugin_components
from app.platform.plugins.artifact_plugins.registry import reset_artifact_plugin_registries
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_succeeded
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-todo-artifact-cards"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_artifact_card_creation_tolerates_generated_unknown_card_metadata(
    db_client,
    tmp_path: Path,
    monkeypatch,
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


def metadata_json(content):
    return {"renderer": "demo-project-artifact", "artifact_kind": "demo_project_artifact"}
'''.strip(),
        prompt_template="Build {{ artifact_kind }} for {{ source_title }}. {{ output_instruction }}",
        html_template="<html><body><h1>{{ content.title }}</h1></body></html>",
        json_schema={
            "type": "object",
            "required": ["artifact_kind", "title"],
            "properties": {
                "artifact_kind": {"const": "demo_project_artifact"},
                "title": {"type": "string"},
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
    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review CMS requirement"},
    )
    assert source_response.status_code == 200
    source_todo_id = source_response.json()["id"]

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
                    "title": "Build CMS publishing workflow",
                    "description": "Created from generated requirement review output.",
                    "todo_type_id": "cms-feature",
                    "artifact_kinds": [
                        "requirement_spec",
                        "ui_review",
                        "test_report",
                        "project:demo_project_artifact",
                    ],
                },
            },
        )

    assert create_response.status_code == 200, create_response.json()
    created = create_response.json()
    assert created["parent_todo_id"] == source_todo_id
    assert created["todo_type_id"] == "default"
    assert created["artifact_kinds"] == ["project:demo_project_artifact"]
    assert created["artifacts"][0]["artifact_id"] == str(artifact_id)
    assert created["artifacts"][0]["purpose"] == "artifact_card"


@pytest.mark.asyncio
async def test_artifact_card_creation_maps_generated_todo_type_alias(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    type_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todo-types/system",
        json={
            "id": "ui-change",
            "name": "UI change",
            "description": "Visible UI behavior or layout change.",
            "agent": "codex",
            "artifact_kinds": ["agent_trace_graph"],
            "dispatch_template": "Implement {{ title }}.",
        },
    )
    assert type_response.status_code == 200

    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review UI requirement"},
    )
    assert source_response.status_code == 200
    source_todo_id = source_response.json()["id"]
    artifact_id = await _create_linked_succeeded_artifact(db_client, client_id, source_todo_id)

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/from-artifact-card",
        params={"project_path": PROJECT_PATH},
        json={
            "artifact_id": str(artifact_id),
            "card": {
                "title": "Improve toolbar filtering",
                "description": "Created from generated requirement review output.",
                "todo_type_id": "ui",
            },
        },
    )

    assert create_response.status_code == 200, create_response.json()
    assert create_response.json()["todo_type_id"] == "ui-change"


@pytest.mark.asyncio
async def test_requirement_review_artifact_card_creation_strips_type_metadata_from_description(
    db_client,
) -> None:
    client_id = await get_local_client_id(db_client)
    type_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todo-types/system",
        json={
            "id": "ui-change",
            "name": "UI change",
            "description": "Visible UI behavior or layout change.",
            "agent": "codex",
            "artifact_kinds": ["agent_trace_graph"],
            "dispatch_template": "Implement {{ title }}.",
        },
    )
    assert type_response.status_code == 200
    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Review CMS requirement"},
    )
    assert source_response.status_code == 200
    artifact_id = await _create_linked_succeeded_artifact(
        db_client,
        client_id,
        source_response.json()["id"],
    )

    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/from-artifact-card",
        params={"project_path": PROJECT_PATH},
        json={
            "artifact_id": str(artifact_id),
            "card": {
                "title": "Confirm CMS scope",
                "description": (
                    "Clarify CMS content types and roles.\n\n"
                    "Recommended todo type: ui-change\n"
                    "Recommended todo type: ui-change"
                ),
                "todo_type_id": "ui-change",
            },
        },
    )

    assert create_response.status_code == 200, create_response.json()
    created = create_response.json()
    assert created["todo_type_id"] == "ui-change"
    assert "Clarify CMS content types and roles." in created["description"]
    assert "Recommended todo type" not in created["description"]


async def _create_linked_succeeded_artifact(db_client, client_id: str, source_todo_id: str):
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
        return artifact.id
