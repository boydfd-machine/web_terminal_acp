from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.unit.test_summary_scheduler_support import *  # noqa: F401,F403
from tests.unit.test_summary_scheduler_support import db_session  # noqa: F401

from app.contexts.workspace.application import project_todo_completion_verification as verification
from app.contexts.workspace.application.project_todo_background_completion import (
    active_processes_look_like_background_work,
)
from app.models import Client, ClientRuntime, ProjectTodo, ProjectTodoStatus, VirtualWindow, WindowStatus


def _patch_completion_upgrade(monkeypatch, calls: list) -> None:
    async def fake_complete(_session, todo, actual_completed_at, actual_window_id, **_kwargs):
        calls.append((actual_completed_at, actual_window_id))
        todo.dispatch_stage = None
        todo.dispatch_error = None

    monkeypatch.setattr(verification, "complete_project_todo_implementation", fake_complete)


@pytest.mark.asyncio
async def test_verification_waits_for_new_agent_completion_after_background_process_exits(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )

    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    client = Client(
        id=uuid4(),
        name="remote",
        runtime=ClientRuntime.remote,
        token_hash="hash",
        owner_user_id="owner-1",
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Remote terminal",
        status=WindowStatus.active,
        agent_activity_latest_completed_at=completed_at,
    )
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path="/tmp/proj",
        title="Delayed task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatch_stage="verifying",
        dispatch_error="waiting for active background process before completion review: sleep 120",
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    upgrade_called = []

    scheduled_calls = []

    def fake_schedule(*args, **kwargs):
        scheduled_calls.append(kwargs)
        return None

    _patch_completion_upgrade(monkeypatch, upgrade_called)
    monkeypatch.setattr(verification, "schedule_todo_completion_verification", fake_schedule)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo.id,
        client_id=client.id,
        completed_at=completed_at,
        window_id=window.id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    assert upgrade_called == []
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.dispatch_error is not None
    assert "waiting for main agent final completion" in todo.dispatch_error
    assert len(scheduled_calls) == 1
    assert scheduled_calls[0]["attempt"] == 1


@pytest.mark.asyncio
async def test_verification_completes_with_new_agent_completion_after_background_process_exits(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )

    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    final_completed_at = completed_at + timedelta(seconds=125)
    client = Client(
        id=uuid4(),
        name="remote",
        runtime=ClientRuntime.remote,
        token_hash="hash",
        owner_user_id="owner-1",
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Remote terminal",
        status=WindowStatus.active,
        agent_activity_latest_completed_at=final_completed_at,
    )
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path="/tmp/proj",
        title="Delayed task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatch_stage="verifying",
        dispatch_error="waiting for active background process before completion review: sleep 120",
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    completed_calls = []

    run_prompt = AsyncMock(
        return_value=verification.VerificationVerdict(
            verdict="complete",
            evidence="agent reported delayed work complete",
            open_processes=[],
        )
    )

    monkeypatch.setattr(verification, "_run_verification_prompt", run_prompt)
    _patch_completion_upgrade(monkeypatch, completed_calls)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo.id,
        client_id=client.id,
        completed_at=completed_at,
        window_id=window.id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    assert completed_calls == [(final_completed_at, window.id)]
    assert run_prompt.await_count == 1
    assert todo.dispatch_stage is None
    assert todo.dispatch_error is None


def test_background_work_detection_defers_wait_commands_without_blocking_dev_servers() -> None:
    assert active_processes_look_like_background_work(["sleep 120"]) is True
    assert active_processes_look_like_background_work(["/usr/bin/timeout 120s done"]) is True
    assert active_processes_look_like_background_work(["bash -lc 'sleep 120; echo done'"]) is True

    assert active_processes_look_like_background_work(["/usr/bin/node dev-server.js"]) is False
    assert active_processes_look_like_background_work(["npm run dev"]) is False


class _CtxManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False
