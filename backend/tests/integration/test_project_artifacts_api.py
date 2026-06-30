from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.models import VirtualWindow
from app.repositories.terminal_artifacts import create_terminal_artifact, mark_artifact_succeeded
from tests.integration.test_window_api_support import get_local_client_id

PROJECT_PATH = "/tmp/project-artifacts"
pytest_plugins = ["tests.integration.test_window_api_support"]


@pytest.mark.asyncio
async def test_project_artifacts_are_grouped_by_kind_with_versions(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    older_time = datetime(2026, 6, 7, 8, 0, tzinfo=UTC)
    newer_time = datetime(2026, 6, 7, 9, 0, tzinfo=UTC)

    async with db_client.session_factory() as session:
        first_window = VirtualWindow(
            id=uuid4(),
            client_id=UUID(client_id),
            title="First journey terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        second_window = VirtualWindow(
            id=uuid4(),
            client_id=UUID(client_id),
            title="Updated journey terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        third_window = VirtualWindow(
            id=uuid4(),
            client_id=UUID(client_id),
            title="Prototype terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add_all([first_window, second_window, third_window])
        old_journey = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=first_window.id,
            source_window_id=first_window.id,
            artifact_scope="project",
            project_path=PROJECT_PATH,
            artifact_kind="user_journey",
            title="Journey v1",
        )
        new_journey = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=second_window.id,
            source_window_id=second_window.id,
            artifact_scope="project",
            project_path=PROJECT_PATH,
            artifact_kind="user_journey",
            title="Journey v2",
        )
        prototype = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=third_window.id,
            source_window_id=third_window.id,
            artifact_scope="project",
            project_path=PROJECT_PATH,
            artifact_kind="low_fi_prototype",
            title="Prototype v1",
        )
        await mark_artifact_succeeded(
            session,
            old_journey,
            content_json={"title": "Journey v1"},
            display_html="<html>journey v1</html>",
        )
        await mark_artifact_succeeded(
            session,
            new_journey,
            content_json={"title": "Journey v2"},
            display_html="<html>journey v2</html>",
        )
        old_journey.created_at = older_time
        old_journey.updated_at = older_time
        old_journey.completed_at = older_time
        new_journey.created_at = newer_time
        new_journey.updated_at = newer_time
        new_journey.completed_at = newer_time
        prototype.created_at = datetime(2026, 6, 7, 8, 30, tzinfo=UTC)
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/projects/artifacts",
        params={"project_path": PROJECT_PATH},
    )

    assert response.status_code == 200
    body = response.json()
    assert [artifact["title"] for artifact in body["artifacts"]] == [
        "Journey v2",
        "Prototype v1",
        "Journey v1",
    ]
    assert [group["artifact_kind"] for group in body["artifact_groups"]] == [
        "user_journey",
        "low_fi_prototype",
    ]
    user_journey_group = body["artifact_groups"][0]
    assert user_journey_group["latest_artifact"]["id"] == str(new_journey.id)
    assert user_journey_group["version_count"] == 2
    assert [version["artifact"]["id"] for version in user_journey_group["versions"]] == [
        str(new_journey.id),
        str(old_journey.id),
    ]
    assert user_journey_group["versions"][0]["version_number"] == 2
    assert user_journey_group["versions"][1]["version_number"] == 1
    assert user_journey_group["versions"][0]["source_window_title"] == "Updated journey terminal"
    assert user_journey_group["versions"][1]["source_window_title"] == "First journey terminal"
