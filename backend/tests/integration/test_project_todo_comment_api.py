import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.config import get_settings
from app.contexts.workspace.application import project_todo_comment as project_todo_comment_service
from app.contexts.workspace.infrastructure.project_todos_repository import link_project_todo_artifact
from app.models import AiSession, Event, EventSourceType, ProjectTodo, ProjectTodoStatus, VirtualWindow
from app.repositories.terminal_artifacts import create_terminal_artifact
from tests.integration.test_window_api_support import (
    codex_message_payload,
    codex_user_message_payload,
    get_local_client_id,
)


PROJECT_PATH = "/tmp/project-todos"
PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS = 5.0
pytest_plugins = ["tests.integration.test_window_api_support"]


async def _wait_for_project_todo_status(
    db_client,
    todo_id: str,
    status: ProjectTodoStatus,
) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.status == status:
                return todo
        await asyncio.sleep(PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"project todo did not reach status {status.value}")


@pytest.mark.asyncio
async def test_comment_project_todo_requeues_existing_terminal_until_review(db_client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", False)
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Apply review feedback"},
    )
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    prompt_started = asyncio.Event()
    allow_prompt_finish = asyncio.Event()
    submitted_prompts: list[dict[str, object]] = []
    observed_status_before_prompt_finish: list[ProjectTodoStatus] = []
    observed_stage_before_prompt_finish: list[str | None] = []

    async def fake_submit_comment_prompt_by_id(**kwargs) -> None:
        submitted_prompts.append({
            "client_id": str(kwargs["client_id"]),
            "window_id": str(kwargs["window_id"]),
            "prompt": kwargs["prompt"],
        })
        await kwargs["on_terminal_ready"]()
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            assert todo is not None
            observed_status_before_prompt_finish.append(todo.status)
            observed_stage_before_prompt_finish.append(todo.dispatch_stage)
        prompt_started.set()
        await allow_prompt_finish.wait()

    monkeypatch.setattr(
        project_todo_comment_service,
        "_submit_comment_prompt_by_id",
        fake_submit_comment_prompt_by_id,
    )
    async with db_client.session_factory() as session:
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Todo worker",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add(window)
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.awaiting_review_at = datetime.now(timezone.utc)
        todo.review_status = "PENDING"
        todo.review_unseen = True
        todo.implementation_worktree_json = {"branch": "agent/old-work"}
        await session.commit()

    comment_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/comment",
        params={"project_path": PROJECT_PATH},
        json={"comment": "Please run another pass with the edge case fixed."},
    )

    assert comment_response.status_code == 200
    started = comment_response.json()
    assert started["status"] == "TODO"
    assert started["assigned_window_id"] == str(window_id)
    assert started["dispatch_stage"] == "STARTING"
    assert started["dispatch_error"] is None
    assert started["awaiting_review_at"] is None
    assert started["review_status"] == "NOT_REQUESTED"
    assert started["review_unseen"] is False
    assert started["implementation_worktree"] is None
    await asyncio.wait_for(prompt_started.wait(), timeout=PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS)
    assert submitted_prompts == [
        {
            "client_id": client_id,
            "window_id": str(window_id),
            "prompt": submitted_prompts[0]["prompt"],
        }
    ]
    assert "follow-up comment" in str(submitted_prompts[0]["prompt"])
    assert "Please run another pass" in str(submitted_prompts[0]["prompt"])
    assert observed_status_before_prompt_finish == [ProjectTodoStatus.todo]
    assert observed_stage_before_prompt_finish == ["TERMINAL_READY"]

    allow_prompt_finish.set()
    dispatched = await _wait_for_project_todo_status(db_client, todo_id, ProjectTodoStatus.dispatched)
    assert dispatched.assigned_window_id == window_id
    assert dispatched.dispatch_stage is None
    assert dispatched.dispatch_error is None
    assert dispatched.dispatched_at is not None
    assert dispatched.review_status == "NOT_REQUESTED"

    completed_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    async with db_client.session_factory() as session:
        window = await session.get(VirtualWindow, window_id)
        assert window is not None
        window.agent_activity_latest_completed_at = completed_at
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    [review_todo] = list_response.json()["todos"]
    assert review_todo["status"] == "AWAITING_REVIEW"
    assert review_todo["review_status"] == "PENDING"
    assert review_todo["review_unseen"] is True


@pytest.mark.asyncio
async def test_comment_project_todo_prompt_includes_referenced_card_context(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    referenced_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Write docs", "description": "Document the card link behavior."},
    )
    assert referenced_response.status_code == 200
    referenced = referenced_response.json()
    source_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Apply review feedback"},
    )
    assert source_response.status_code == 200
    todo_id = source_response.json()["id"]
    window_id = uuid4()
    referenced_window_id = uuid4()
    referenced_artifact_window_id = uuid4()
    referenced_artifact_id = None
    base_time = datetime.now(timezone.utc)
    prompt_submitted = asyncio.Event()
    submitted_prompts: list[str] = []

    async def fake_submit_comment_prompt_by_id(**kwargs) -> None:
        submitted_prompts.append(kwargs["prompt"])
        await kwargs["on_terminal_ready"]()
        prompt_submitted.set()

    monkeypatch.setattr(
        project_todo_comment_service,
        "_submit_comment_prompt_by_id",
        fake_submit_comment_prompt_by_id,
    )
    async with db_client.session_factory() as session:
        referenced_window = VirtualWindow(
            id=referenced_window_id,
            client_id=UUID(client_id),
            title="Docs terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        artifact_window = VirtualWindow(
            id=referenced_artifact_window_id,
            client_id=UUID(client_id),
            title="Docs artifact terminal",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Todo worker",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add_all([referenced_window, artifact_window, window])
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="comment-reference-session",
            virtual_window_id=referenced_window_id,
        )
        session.add(ai_session)
        await session.flush()
        referenced_todo = await session.get(ProjectTodo, UUID(referenced["id"]))
        assert referenced_todo is not None
        referenced_todo.assigned_window_id = referenced_window_id
        artifact = await create_terminal_artifact(
            session,
            client_id=UUID(client_id),
            virtual_window_id=referenced_artifact_window_id,
            source_window_id=referenced_window_id,
            artifact_kind="agent_trace_graph",
            title="Docs trace",
        )
        referenced_artifact_id = artifact.id
        await link_project_todo_artifact(session, referenced_todo, artifact.id, purpose="review")
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="comment-reference-session",
                    kind="response_item",
                    virtual_window_id=referenced_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload("Use description to document links"),
                    fingerprint="todo-comment-reference-user",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="comment-reference-session",
                    kind="response_item",
                    virtual_window_id=referenced_window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_message_payload("Documented linked card sessions"),
                    fingerprint="todo-comment-reference-agent",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.awaiting_review_at = datetime.now(timezone.utc)
        todo.review_status = "PENDING"
        await session.commit()

    comment_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/comment",
        params={"project_path": PROJECT_PATH},
        json={"comment": f"Please check @[其它需求：$Write docs|{referenced['id']}] before retrying."},
    )

    assert comment_response.status_code == 200
    await asyncio.wait_for(prompt_submitted.wait(), timeout=PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS)
    assert len(submitted_prompts) == 1
    assert "Please check @[其它需求：$Write docs|" in submitted_prompts[0]
    assert "# References" in submitted_prompts[0]
    assert "## Write docs Card" in submitted_prompts[0]
    assert "### Sessions" in submitted_prompts[0]
    assert "### artifacts" in submitted_prompts[0]
    assert "### terminals" in submitted_prompts[0]
    assert "Document the card link behavior." not in submitted_prompts[0]
    assert "Use description to document links" in submitted_prompts[0]
    assert "Documented linked card sessions" in submitted_prompts[0]
    assert f"Docs terminal ({referenced_window_id})" in submitted_prompts[0]
    assert f"Docs trace (artifact: {referenced_artifact_id})" in submitted_prompts[0]
    assert f"Docs artifact terminal ({referenced_artifact_window_id})" in submitted_prompts[0]


@pytest.mark.asyncio
async def test_comment_project_todo_updates_requested_artifact_kinds(db_client, monkeypatch) -> None:
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Apply review feedback", "artifact_kinds": ["agent_trace_graph"]},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    prompt_submitted = asyncio.Event()

    async def fake_submit_comment_prompt_by_id(**kwargs) -> None:
        await kwargs["on_terminal_ready"]()
        prompt_submitted.set()

    monkeypatch.setattr(
        project_todo_comment_service,
        "_submit_comment_prompt_by_id",
        fake_submit_comment_prompt_by_id,
    )
    async with db_client.session_factory() as session:
        window = VirtualWindow(
            id=window_id,
            client_id=UUID(client_id),
            title="Todo worker",
            cwd=PROJECT_PATH,
            shell_command="codex",
        )
        session.add(window)
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        todo.assigned_agent = "codex"
        todo.awaiting_review_at = datetime.now(timezone.utc)
        todo.review_status = "PENDING"
        await session.commit()

    comment_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/comment",
        params={"project_path": PROJECT_PATH},
        json={"comment": "Please retry without creating an artifact.", "artifact_kinds": []},
    )

    assert comment_response.status_code == 200
    started = comment_response.json()
    assert started["status"] == "TODO"
    assert started["artifact_kinds"] == []
    await asyncio.wait_for(prompt_submitted.wait(), timeout=PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS)
