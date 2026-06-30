import asyncio
from uuid import UUID, uuid4

import pytest

from app.contexts.workspace.application import project_todo_dispatch_after as dispatch_after_service
from app.contexts.windows.infrastructure.repository import create_window
from app.models import Client, ProjectTodo, ProjectTodoStatus
from app.repositories.clients import create_client
from tests.integration.test_window_api_support import DbClient, get_local_client_id

pytest_plugins = ["tests.integration.test_window_api_support"]


async def _create_source_window(db_client: DbClient) -> tuple[str, str]:
    local_client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        source = await create_window(
            session,
            UUID(local_client_id),
            cwd="/workspace/source",
            shell_command="/bin/bash",
            tmux_session="test_pool",
            tmux_window_id="@1",
        )
        source_id = str(source.id)
        await session.commit()
    return local_client_id, source_id


def _source_headers(client_id: str, window_id: str) -> dict[str, str]:
    return {
        "X-Web-Terminal-Source-Client-Id": client_id,
        "X-Web-Terminal-Source-Window-Id": window_id,
    }


async def _wait_for_project_todo_status(
    db_client: DbClient,
    todo_id: str,
    status: ProjectTodoStatus,
) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.status == status:
                return todo
        await asyncio.sleep(0.025)
    raise AssertionError(f"project todo did not reach status {status.value}")


@pytest.mark.asyncio
async def test_agent_ops_can_create_patch_and_dispatch_project_todo(
    db_client: DbClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    async with db_client.session_factory() as session:
        source_client = await session.get(Client, UUID(client_id))
        assert source_client is not None
        source_client.owner_user_id = "owner-a"
        target_client, _token = await create_client(
            session,
            name=f"Target {uuid4()}",
            owner_user_id="owner-a",
        )
        target_client_id = str(target_client.id)
        await session.commit()
    dispatched_prompts: list[dict[str, object]] = []

    async def fake_create_virtual_window_for_client(client, payload, session, *_args, **_kwargs):
        window = await create_window(
            session,
            client.id,
            cwd=payload.cwd,
            shell_command=payload.agent_launch.command,
            remote_session_id="remote-session",
            remote_window_id="remote-window",
        )
        return type("Result", (), {"window": window})()

    async def fake_dispatch_project_todo_prompt(**kwargs) -> None:
        dispatched_prompts.append(
            {
                "client_id": str(kwargs["client_id"]),
                "window_id": str(kwargs["window_id"]),
                "prompt": kwargs["prompt"],
                "submit_prompt": kwargs["submit_prompt"],
            }
        )

    monkeypatch.setattr(
        dispatch_after_service,
        "dispatch_project_todo_prompt",
        fake_dispatch_project_todo_prompt,
    )
    monkeypatch.setattr(
        dispatch_after_service,
        "create_virtual_window_for_client",
        fake_create_virtual_window_for_client,
    )
    headers = _source_headers(client_id, source_window_id)
    params = {"project_path": "/workspace/project", "target_client_id": target_client_id}
    create_response = await db_client.post(
        "/api/agent-ops/project-todos",
        headers=headers,
        params=params,
        json={"title": "Ops-created card", "description": "Create from managed shell"},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    todo_id = created["id"]
    assert created["client_id"] == target_client_id
    assert created["project_path"] == "/workspace/project"
    assert created["title"] == "Ops-created card"

    patch_response = await db_client.patch(
        f"/api/agent-ops/project-todos/{todo_id}",
        headers=headers,
        params=params,
        json={"title": "Ops-patched card", "description": None},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["title"] == "Ops-patched card"
    assert patched["description"] is None

    dispatch_response = await db_client.post(
        f"/api/agent-ops/project-todos/{todo_id}/dispatch",
        headers=headers,
        params=params,
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": None,
            },
            "dispatch_mode": "compose",
            "prompt": "Dispatch from ops CLI",
        },
    )
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["dispatch_stage"] == "STARTING"

    for _ in range(200):
        if dispatched_prompts:
            break
        await asyncio.sleep(0.025)
    assert dispatched_prompts == [
        {
            "client_id": target_client_id,
            "window_id": dispatched_prompts[0]["window_id"],
            "prompt": dispatched_prompts[0]["prompt"],
            "submit_prompt": False,
        }
    ]
    assert "Dispatch from ops CLI" in dispatched_prompts[0]["prompt"]
    dispatched = await _wait_for_project_todo_status(
        db_client, todo_id, ProjectTodoStatus.dispatched
    )
    assert dispatched.assigned_window_id is not None


@pytest.mark.asyncio
async def test_agent_ops_project_todo_writes_reject_cross_owner_target_client(
    db_client: DbClient,
) -> None:
    client_id, source_window_id = await _create_source_window(db_client)
    async with db_client.session_factory() as session:
        source_client = await session.get(Client, UUID(client_id))
        assert source_client is not None
        source_client.owner_user_id = "owner-a"
        other_client, _token = await create_client(
            session,
            name=f"Remote {uuid4()}",
            owner_user_id="owner-b",
        )
        same_owner_client, _token = await create_client(
            session,
            name=f"Same owner {uuid4()}",
            owner_user_id="owner-a",
        )
        await session.commit()

    headers = _source_headers(client_id, source_window_id)
    project_path = "/workspace/remote-project"
    allowed_create = await db_client.post(
        "/api/agent-ops/project-todos",
        headers=headers,
        params={"project_path": project_path, "target_client_id": str(same_owner_client.id)},
        json={"title": "Same owner target"},
    )
    assert allowed_create.status_code == 200
    assert allowed_create.json()["client_id"] == str(same_owner_client.id)

    denied_create = await db_client.post(
        "/api/agent-ops/project-todos",
        headers=headers,
        params={"project_path": project_path, "target_client_id": str(other_client.id)},
        json={"title": "Cross owner target"},
    )
    victim_create = await db_client.post(
        f"/api/clients/{other_client.id}/projects/todos",
        params={"project_path": project_path},
        json={"title": "Victim owner card"},
    )
    assert victim_create.status_code == 200
    victim_todo_id = victim_create.json()["id"]
    denied_patch = await db_client.patch(
        f"/api/agent-ops/project-todos/{victim_todo_id}",
        headers=headers,
        params={"project_path": project_path, "target_client_id": str(other_client.id)},
        json={"title": "Cross owner patch"},
    )
    denied_dispatch = await db_client.post(
        f"/api/agent-ops/project-todos/{victim_todo_id}/dispatch",
        headers=headers,
        params={"project_path": project_path, "target_client_id": str(other_client.id)},
        json={
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "config": None,
                "profile_id": None,
            },
            "dispatch_mode": "compose",
            "prompt": "Cross owner dispatch",
        },
    )

    assert denied_create.status_code == 404
    assert denied_create.json()["detail"] == "client not found"
    assert denied_patch.status_code == 404
    assert denied_patch.json()["detail"] == "client not found"
    assert denied_dispatch.status_code == 404
    assert denied_dispatch.json()["detail"] == "client not found"
