from pathlib import Path
from uuid import UUID

import pytest

from app.models import ProjectTodo
from app.platform.plugins.artifact_plugins.management import save_artifact_plugin_source
from app.platform.plugins.artifact_plugins.registry import reset_artifact_plugin_registries
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-todo-types"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_system_project_todo_types_can_bind_default_agent(
    db_client,
    tmp_path: Path,
    monkeypatch,
    request,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    client_id = await get_local_client_id(db_client)
    reset_artifact_plugin_registries()
    request.addfinalizer(reset_artifact_plugin_registries)
    save_artifact_plugin_source(
        "terminal",
        '''
from app.platform.plugins.artifact_plugins.types import TerminalArtifactRender


class DeepResearchReportPlugin:
    artifact_kind = "deep_research_report"
    label = "Deep Research Report"
    default_title = "Deep research report"

    def build_prompt(self, *, source_title, user_prompt=None, output_path=None):
        return f"Build research report for {source_title}"

    def parse_output(self, output):
        return {"text": output}

    def render(self, content_json):
        return TerminalArtifactRender(
            content_json=content_json,
            display_html="<html><body>report</body></html>",
            metadata_json={"renderer": "deep-research-report"},
        )


def create_plugin():
    return DeepResearchReportPlugin()
'''.strip(),
        allow_overwrite=True,
        home=home,
    )

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todo-types",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    assert list_response.json()["todo_types"] == []

    create_type_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todo-types/system",
        json={
            "id": "research",
            "name": "Research",
            "description": "Collect background and references.",
            "agent": "codex",
            "agent_profile_id": "research-profile",
            "artifact_kinds": ["agent_trace_graph"],
            "input_artifact_ids": [" artifact-current ", "artifact-flow"],
            "dispatch_template": "Research {{ title }} in {{ project_path }}.\n\n{{ description }}",
        },
    )
    assert create_type_response.status_code == 200
    todo_type = create_type_response.json()
    assert todo_type["id"] == "research"
    assert todo_type["scope"] == "system"
    assert todo_type["project_path"] is None
    assert todo_type["agent"] == "codex"
    assert todo_type["agent_profile_id"] == "research-profile"
    assert todo_type["artifact_kinds"] == ["agent_trace_graph"]
    assert todo_type["input_artifact_ids"] == ["artifact-current", "artifact-flow"]
    assert todo_type["dispatch_template"] == "Research {{ title }} in {{ project_path }}.\n\n{{ description }}"

    create_todo_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={
            "title": "Survey existing options",
            "todo_type_id": "research",
        },
    )
    assert create_todo_response.status_code == 200
    created = create_todo_response.json()
    assert created["todo_type"]["id"] == "research"
    assert created["todo_type"]["agent"] == "codex"
    assert created["todo_type"]["artifact_kinds"] == ["agent_trace_graph"]
    assert created["todo_type"]["input_artifact_ids"] == ["artifact-current", "artifact-flow"]
    assert created["todo_type"]["dispatch_template"] == (
        "Research {{ title }} in {{ project_path }}.\n\n{{ description }}"
    )
    assert created["assigned_agent"] == "codex"
    assert created["agent_profile_id"] == "research-profile"
    assert created["artifact_kinds"] == ["agent_trace_graph"]
    assert created["input_artifact_ids"] == ["artifact-current", "artifact-flow"]

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{created['id']}",
        params={"project_path": PROJECT_PATH},
        json={"input_artifact_ids": ["artifact-explicit", " artifact-explicit "]},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["input_artifact_ids"] == ["artifact-explicit"]

    dispatch_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{created['id']}/dispatch",
        params={"project_path": PROJECT_PATH},
        json={
            "agent_launch": {"agent": "codex", "command": "codex", "config": None, "profile_id": None},
            "dispatch_mode": "compose",
            "output_language": "中文",
        },
    )
    assert dispatch_response.status_code == 200
    dispatch_prompt = dispatch_response.json()["dispatch_prompt"]
    assert "# Input artifacts" in dispatch_prompt
    assert "- artifact-explicit" in dispatch_prompt
    assert "--artifact-scope project" in dispatch_prompt
    assert f"--project-path {PROJECT_PATH}" in dispatch_prompt

    list_types_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todo-types",
        params={"project_path": PROJECT_PATH},
    )
    assert list_types_response.status_code == 200
    assert [todo_type["id"] for todo_type in list_types_response.json()["todo_types"]] == ["research"]

    async with db_client.session_factory() as session:
        stored = await session.get(ProjectTodo, UUID(created["id"]))
    assert stored is not None
    assert stored.todo_type_id == "research"
    assert stored.artifact_kinds_json == ["agent_trace_graph"]
    assert stored.input_artifact_ids_json == ["artifact-explicit"]
