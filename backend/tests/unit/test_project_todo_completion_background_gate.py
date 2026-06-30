from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.unit.test_summary_scheduler_support import *  # noqa: F401,F403
from tests.unit.test_summary_scheduler_support import db_session  # noqa: F401

from app.contexts.workspace.application import project_todo_completion_verification as verification
from app.contexts.workspace.application.project_todo_completion_background_gate import (
    background_completion_review_time,
    final_completion_wait_started_at,
)
from app.contexts.workspace.application.project_todo_background_completion import final_completion_waiting_error
from app.models import Client, ClientRuntime, ProjectTodo, ProjectTodoStatus, VirtualWindow, WindowStatus


def _patch_completion_upgrade(monkeypatch, calls: list[bool]) -> None:
    async def fake_complete(_session, todo, *_args, **_kwargs):
        calls.append(True)
        todo.dispatch_stage = None
        todo.dispatch_error = None

    monkeypatch.setattr(verification, "complete_project_todo_implementation", fake_complete)


@pytest.mark.asyncio
async def test_background_incomplete_verdict_waits_for_fresh_agent_completion(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(True, ["npm exec mcp-searxng"])),
    )
    run_prompt = AsyncMock(
        side_effect=[
            verification.VerificationVerdict(
                verdict="incomplete",
                evidence="timer fired but agent did not report execution complete",
                open_processes=["npm exec mcp-searxng"],
            ),
            verification.VerificationVerdict(
                verdict="complete",
                evidence="agent record projection now includes the final completion report",
                open_processes=["npm exec mcp-searxng"],
            ),
        ]
    )
    monkeypatch.setattr(verification, "_run_verification_prompt", run_prompt)

    client = Client(
        id=uuid4(),
        name="remote",
        runtime=ClientRuntime.remote,
        token_hash="hash",
        owner_user_id="owner-1",
    )
    db_session.add(client)
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    background_followup_at = datetime(2026, 6, 13, 10, 2, tzinfo=timezone.utc)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Remote terminal",
        status=WindowStatus.active,
        agent_activity_latest_completed_at=background_followup_at,
    )
    todo = ProjectTodo(
        id=uuid4(),
        client_id=client.id,
        project_path="/tmp/proj",
        title="Delayed task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatch_stage="verifying",
        dispatch_error=verification.background_work_waiting_error(["sleep 120"]),
    )
    db_session.add_all([window, todo])
    await db_session.flush()

    scheduled_calls = []
    upgrade_called = []

    def fake_schedule(*args, **kwargs):
        scheduled_calls.append(kwargs)
        return None

    monkeypatch.setattr(verification, "schedule_todo_completion_verification", fake_schedule)
    _patch_completion_upgrade(monkeypatch, upgrade_called)

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

    assert todo.dispatch_error is not None
    assert "incomplete" in todo.dispatch_error
    assert scheduled_calls

    next_call = scheduled_calls[-1]
    await verification._verify_todo_completion(
        todo.id,
        client_id=client.id,
        completed_at=next_call["completed_at"],
        window_id=window.id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=next_call["attempt"],
    )

    assert run_prompt.await_count == 2
    assert upgrade_called == [True]
    assert todo.dispatch_stage is None
    assert todo.dispatch_error is None


@pytest.mark.asyncio
async def test_final_completion_wait_recheck_runs_auxiliary_review(db_session):
    completed_at = datetime(2026, 6, 13, 10, 2, tzinfo=timezone.utc)
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
        dispatch_error=final_completion_waiting_error(completed_at),
    )
    db_session.add_all([client, window, todo])
    await db_session.flush()

    review = await background_completion_review_time(
        db_session,
        todo,
        client_id=client.id,
        window_id=window.id,
        completed_at=completed_at,
        dispatch_stage="verifying",
    )

    assert review is not None
    assert review.waited_for_background_work is True
    assert review.completed_at == completed_at


def test_final_completion_wait_started_at_parses_retry_error() -> None:
    completed_at = datetime(2026, 6, 13, 10, 2, tzinfo=timezone.utc)
    dispatch_error = verification.background_verification_incomplete_waiting_error(
        completed_at,
        attempt=1,
        verdict=verification.VerificationVerdict(
            verdict="incomplete",
            evidence="agent record projection lagged",
            open_processes=[],
        ),
    )

    assert final_completion_wait_started_at(dispatch_error) == completed_at
    assert final_completion_wait_started_at("verification attempt 1 incomplete") is None
    assert final_completion_wait_started_at(None) is None


class _CtxManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False
