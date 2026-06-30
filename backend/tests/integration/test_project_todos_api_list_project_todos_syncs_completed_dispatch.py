import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.config import get_settings
from app.contexts.workspace.infrastructure.project_todo_completion_repository import _mark_implementation_completed
from app.models import (
    Event,
    EventSourceType,
    GitWorktreeRun,
    ProjectTodo,
    ProjectTodoStatus,
    VirtualWindow,
)
from app.services.summary_scheduler import schedule_summary_after_agent_activity
from tests.integration.test_window_api_support import (
    codex_completion_payload,
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


async def _wait_for_project_todo_stage(db_client, todo_id: str, stage: str) -> ProjectTodo:
    for _ in range(200):
        async with db_client.session_factory() as session:
            todo = await session.get(ProjectTodo, UUID(todo_id))
            if todo is not None and todo.dispatch_stage == stage:
                return todo
        await asyncio.sleep(PROJECT_TODO_ASYNC_TEST_TIMEOUT_SECONDS / 200)
    raise AssertionError(f"project todo did not reach dispatch stage {stage}")

@pytest.mark.asyncio
async def test_project_todo_responses_allow_completion_verifying_stage(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    project_path = f"{PROJECT_PATH}/verifying-stage"
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
        json={"title": "Verify completion"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.dispatched
        todo.dispatch_stage = "verifying"
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
    )
    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["dispatch_stage"] == "verifying"

    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": project_path},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["dispatch_stage"] == "verifying"


@pytest.mark.asyncio
async def test_completion_clears_verifying_dispatch_stage(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    project_path = f"{PROJECT_PATH}/completion-clears-stage"
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
        json={"title": "Clear verifying stage"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    completed_at = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.dispatched
        todo.dispatch_stage = "verifying"
        generations = await _mark_implementation_completed(
            session,
            todo,
            completed_at,
            None,
            remote_client_available=None,
        )
        assert generations == []
        await session.commit()

    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": project_path},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "AWAITING_REVIEW"
    assert detail["dispatch_stage"] is None
    assert detail["dispatch_error"] is None


@pytest.mark.asyncio
async def test_project_todo_responses_hide_stale_dispatch_stage_after_review(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    project_path = f"{PROJECT_PATH}/stale-stage-after-review"
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
        json={"title": "Hide stale stage"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]

    async with db_client.session_factory() as session:
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.dispatch_stage = "verifying"
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
    )
    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["status"] == "AWAITING_REVIEW"
    assert listed["dispatch_stage"] is None

    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": project_path},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["dispatch_stage"] is None


@pytest.mark.asyncio
async def test_moving_review_todo_back_to_todo_clears_stale_dispatch_state(db_client) -> None:
    client_id = await get_local_client_id(db_client)
    project_path = f"{PROJECT_PATH}/review-back-to-todo-clears-stage"
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
        json={"title": "Say hi"},
    )
    assert create_response.status_code == 200
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    reviewed_at = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        session.add(
            VirtualWindow(
                id=window_id,
                client_id=UUID(client_id),
                title="Claude worker",
                cwd=project_path,
                shell_command="claude",
            )
        )
        todo = await session.get(ProjectTodo, UUID(todo_id))
        assert todo is not None
        todo.status = ProjectTodoStatus.awaiting_review
        todo.assigned_window_id = window_id
        todo.dispatch_stage = "verifying"
        todo.dispatch_error = "verification attempt 1 incomplete: still running"
        todo.dispatched_at = reviewed_at
        todo.awaiting_review_at = reviewed_at
        todo.completed_at = reviewed_at
        todo.review_status = "PENDING"
        todo.review_unseen = True
        todo.needs_human_review = True
        todo.review_window_id = uuid4()
        todo.review_prompt = "Review previous work"
        todo.review_dispatched_at = reviewed_at
        todo.reviewed_at = reviewed_at
        todo.implementation_worktree_json = {"branch": "agent/say-hi"}
        await session.commit()

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": project_path},
        json={"status": "TODO", "sort_order": 99},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["status"] == "TODO"
    assert patched["dispatch_stage"] is None
    assert patched["dispatch_error"] is None
    assert patched["dispatched_at"] is None
    assert patched["awaiting_review_at"] is None
    assert patched["completed_at"] is None
    assert patched["review_status"] == "NOT_REQUESTED"
    assert patched["review_unseen"] is False
    assert patched["needs_human_review"] is False
    assert patched["review_window_id"] is None
    assert patched["review_prompt"] is None
    assert patched["review_dispatched_at"] is None
    assert patched["reviewed_at"] is None
    assert patched["implementation_worktree"] is None

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": project_path},
    )
    assert list_response.status_code == 200
    [listed] = list_response.json()["todos"]
    assert listed["status"] == "TODO"
    assert listed["dispatch_stage"] is None
    assert listed["review_status"] == "NOT_REQUESTED"

    async with db_client.session_factory() as session:
        stored = await session.get(ProjectTodo, UUID(todo_id))
    assert stored is not None
    assert stored.status == ProjectTodoStatus.todo
    assert stored.dispatch_stage is None
    assert stored.dispatch_error is None
    assert stored.dispatched_at is None
    assert stored.awaiting_review_at is None
    assert stored.completed_at is None
    assert stored.review_status == "NOT_REQUESTED"
    assert stored.review_window_id is None
    assert stored.implementation_worktree_json is None


@pytest.mark.asyncio
async def test_list_project_todos_syncs_completed_dispatch_to_review(db_client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "project_todo_completion_verification_enabled", False)
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
        json={"title": "Fix review flow"},
    )
    todo_id = create_response.json()["id"]
    window_id = uuid4()
    dispatched_at = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    completed_at = dispatched_at + timedelta(minutes=3)
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
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = window_id
        todo.dispatched_at = dispatched_at
        session.add(
            GitWorktreeRun(
                client_id=UUID(client_id),
                virtual_window_id=window_id,
                command_sequence="worktree:baseline",
                status="completed",
                worktree_root="/tmp/project-todos/.worktrees/review-flow",
                main_repo_root="/tmp/project-todos",
                end_snapshot_json={
                    "branch": "agent/review-flow",
                    "merge_status": "unmerged",
                    "merge_status_reason": "head_not_merged_to_main",
                    "merged_to_main": False,
                    "main_branch": "main",
                },
                session_diff_json={
                    "has_changes": True,
                    "start_head": "base",
                    "end_head": "feature",
                    "commits": [
                        {
                            "sha": "feature",
                            "short_sha": "feature",
                            "subject": "Fix review flow",
                            "files": [{"path": "backend/app.py", "status": "modified"}],
                        }
                    ],
                    "files": [{"path": "backend/app.py", "status": "modified"}],
                },
            )
        )
        await session.commit()

    async with db_client.session_factory() as session:
        window = await session.get(VirtualWindow, window_id)
        assert window is not None
        event = Event(
            client_id=UUID(client_id),
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="event_msg",
            virtual_window_id=window_id,
            payload_json=codex_completion_payload(timestamp=completed_at),
            fingerprint="project-todo-completion-sync",
            created_at=completed_at,
        )
        session.add(event)
        await session.flush()
        await schedule_summary_after_agent_activity(session, window, event=event)
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    await _wait_for_project_todo_status(db_client, todo_id, ProjectTodoStatus.awaiting_review)
    list_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos",
        params={"project_path": PROJECT_PATH},
    )
    assert list_response.status_code == 200
    [todo] = list_response.json()["todos"]
    assert todo["status"] == "AWAITING_REVIEW"
    assert todo["review_status"] == "PENDING"
    assert todo["review_unseen"] is True
    detail_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["awaiting_review_at"] is not None
    assert todo["implementation_worktree"]["worktree_root"] == "/tmp/project-todos/.worktrees/review-flow"
    assert todo["implementation_worktree"]["commits"][0]["subject"] == "Fix review flow"
    assert todo["implementation_worktree"]["merge_status"] == "unmerged"
    assert todo["implementation_worktree"]["merged_to_main"] is False
    assert todo["implementation_worktree"]["merge_attention_required"] is True
    snapshots_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/work-snapshots",
        params={"project_path": PROJECT_PATH},
    )
    assert snapshots_response.status_code == 200
    [snapshot] = snapshots_response.json()["work_snapshots"]
    assert snapshot["window_id"] == str(window_id)
    assert snapshot["role"] == "implementation"
    assert snapshot["branch_name"] == "agent/review-flow"
    assert snapshot["base_sha"] == "base"
    assert snapshot["head_sha"] == "feature"
    assert snapshot["commit_shas"] == ["feature"]
    assert snapshot["changed_files"] == [
        {
            "path": "backend/app.py",
            "old_path": None,
            "status": "modified",
            "additions": None,
            "deletions": None,
        }
    ]
    assert snapshot["dirty_state"] == "clean"
    targets_response = await db_client.get(
        f"/api/clients/{client_id}/projects/todos/{todo_id}/review-targets",
        params={"project_path": PROJECT_PATH},
    )
    assert targets_response.status_code == 200
    [target] = targets_response.json()["review_targets"]
    assert target["provider"] == "LOCAL_CARD"
    assert target["status"] == "OPEN"
    assert target["work_snapshot_id"] == snapshot["id"]
    assert target["base_sha"] == "base"
    assert target["head_sha"] == "feature"

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/projects/todos/{todo_id}",
        params={"project_path": PROJECT_PATH},
        json={"review_unseen": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["review_unseen"] is False
