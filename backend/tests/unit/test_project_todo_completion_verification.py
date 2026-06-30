from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from tests.unit.test_summary_scheduler_support import *  # noqa: F401,F403
from tests.unit.test_summary_scheduler_support import db_session  # noqa: F401

from app.contexts.workspace.application import project_todo_completion_verification as verification
from app.contexts.terminal_runtime.application.agent_task_runner import AgentTaskResult
from app.models import Client, ClientRuntime, ProjectTodo, ProjectTodoStatus, VirtualWindow, WindowStatus


def _patch_completion_upgrade(monkeypatch, calls: list[bool]) -> None:
    async def fake_complete(_session, todo, *_args, **_kwargs):
        calls.append(True)
        todo.dispatch_stage = None
        todo.dispatch_error = None

    monkeypatch.setattr(verification, "complete_project_todo_implementation", fake_complete)


@pytest.mark.asyncio
async def test_verification_skips_upgrade_when_no_active_process(db_session, monkeypatch):
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )
    todo_id = uuid4()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)

    upgrade_called = []
    _patch_completion_upgrade(monkeypatch, upgrade_called)

    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
    )
    db_session.add(todo)
    await db_session.flush()

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    assert upgrade_called == [True]
    assert todo.dispatch_stage is None


@pytest.mark.asyncio
async def test_verification_uses_remote_active_processes_as_background_work(db_session, monkeypatch):
    run_prompt = AsyncMock(
        return_value=verification.VerificationVerdict(
            verdict="incomplete",
            evidence="background agent task still running",
            open_processes=["recent agent work presence"],
        )
    )
    monkeypatch.setattr(
        verification,
        "_run_verification_prompt",
        run_prompt,
    )

    todo_id = uuid4()
    client = Client(
        id=uuid4(),
        name="remote",
        runtime=ClientRuntime.remote,
        token_hash="hash",
        owner_user_id="owner-1",
    )
    db_session.add(client)
    await db_session.flush()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client.id,
        title="Remote terminal",
        status=WindowStatus.active,
        remote_session_id="remote-session",
        remote_window_id="@9",
    )
    db_session.add(window)
    await db_session.flush()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        id=todo_id,
        client_id=client.id,
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window.id,
        dispatch_stage="verifying",
    )
    db_session.add(todo)
    await db_session.flush()

    scheduled_calls = []

    def fake_schedule(*args, **kwargs):
        scheduled_calls.append(kwargs)
        return None

    monkeypatch.setattr(verification, "schedule_todo_completion_verification", fake_schedule)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    class FakeRemoteRuntime:
        async def active_processes(self, runtime_window, *, local_window_id):
            assert runtime_window.session_id == "remote-session"
            assert runtime_window.window_id == "@9"
            assert local_window_id == window.id
            return ["sleep 120"]

    await verification._verify_todo_completion(
        todo_id,
        client_id=client.id,
        completed_at=completed_at,
        window_id=window.id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=object(),
        remote_runtime_factory=lambda _client_id, _registry: FakeRemoteRuntime(),
        attempt=1,
    )

    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_error is not None
    assert "sleep 120" in todo.dispatch_error
    assert run_prompt.await_count == 0
    assert scheduled_calls[0]["attempt"] == 1
    assert scheduled_calls[0]["delay_seconds"] > 0


@pytest.mark.asyncio
async def test_verification_skips_aux_agent_when_active_process_is_not_background_work(db_session, monkeypatch):
    """Active processes that are NOT background work (sleep/timeout/etc.) must
    NOT trigger the aux agent. The aux terminal is heavy (spawns a new ephemeral
    window + agent) and should only run when the agent has actual background
    work still running, or after waiting for background work to finish.

    Reproduces the "say hi" regression: an active dev-server or agent
    infrastructure process was treated as "needs verification" and the aux
    agent was invoked, briefly moving the card to "waiting" before review.
    """
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(True, ["/usr/bin/node dev-server.js"])),
    )
    run_prompt = AsyncMock(return_value=verification.VerificationVerdict(
        verdict="complete",
        evidence="should not be called",
        open_processes=["/usr/bin/node dev-server.js"],
    ))
    monkeypatch.setattr(verification, "_run_verification_prompt", run_prompt)

    todo_id = uuid4()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    upgrade_called = []
    _patch_completion_upgrade(monkeypatch, upgrade_called)

    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
    )
    db_session.add(todo)
    await db_session.flush()

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    # The todo should be marked complete WITHOUT invoking the aux agent.
    assert run_prompt.await_count == 0
    assert upgrade_called == [True]
    assert todo.dispatch_stage is None
    assert todo.dispatch_error is None


@pytest.mark.asyncio
async def test_verification_completes_after_prompt(db_session, monkeypatch):
    """After waiting for background work to finish, the aux agent runs and
    its "complete" verdict moves the todo to review.

    This is the supported aux-agent path: bg work was previously detected,
    we deferred, and now the aux agent verifies final completion. The aux
    agent must NOT be triggered merely because a non-bg-work process is
    active (see test_verification_skips_aux_agent_when_active_process_is_not_background_work).
    """
    from datetime import datetime, timezone
    from app.contexts.workspace.application.project_todo_background_completion import (
        FINAL_COMPLETION_WAITING_PREFIX,
    )

    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )
    monkeypatch.setattr(
        verification,
        "_run_verification_prompt",
        AsyncMock(return_value=verification.VerificationVerdict(
            verdict="complete",
            evidence="background task finished and main agent reported completion",
            open_processes=[],
        )),
    )

    todo_id = uuid4()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    final_wait_error = (
        f"{FINAL_COMPLETION_WAITING_PREFIX}: last agent completion at "
        f"{completed_at.isoformat()}"
    )
    upgrade_called = []
    _patch_completion_upgrade(monkeypatch, upgrade_called)

    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
        dispatch_error=final_wait_error,
    )
    db_session.add(todo)
    await db_session.flush()

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    assert upgrade_called == [True]
    assert todo.dispatch_stage is None
    assert todo.dispatch_error is None


@pytest.mark.asyncio
async def test_verification_does_not_complete_while_background_process_still_running(db_session, monkeypatch):
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(True, ["sleep 120"])),
    )
    run_prompt = AsyncMock(return_value=verification.VerificationVerdict(
        verdict="complete",
        evidence="main agent said the delayed task was started",
        open_processes=["sleep 120"],
    ))
    monkeypatch.setattr(
        verification,
        "_run_verification_prompt",
        run_prompt,
    )

    todo_id = uuid4()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Delayed task",
        description="Start a background program, report it started, then report completion after 120 seconds.",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
    )
    db_session.add(todo)
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
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
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
    assert "sleep 120" in todo.dispatch_error
    assert len(scheduled_calls) == 1
    assert scheduled_calls[0]["attempt"] == 1
    assert scheduled_calls[0]["delay_seconds"] > 0
    assert run_prompt.await_count == 0


@pytest.mark.asyncio
async def test_verification_blocked_after_max_attempts(db_session, monkeypatch):
    """After waiting for background work, when the aux agent fails to confirm
    completion within max_attempts, the todo is marked blocked (not looped
    forever)."""
    from app.contexts.workspace.application.project_todo_background_completion import (
        FINAL_COMPLETION_WAITING_PREFIX,
    )

    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )
    monkeypatch.setattr(
        verification,
        "_run_verification_prompt",
        AsyncMock(return_value=verification.VerificationVerdict(
            verdict="incomplete",
            evidence="still broken",
            open_processes=[],
        )),
    )

    todo_id = uuid4()
    completed_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    final_wait_error = (
        f"{FINAL_COMPLETION_WAITING_PREFIX}: last agent completion at "
        f"{completed_at.isoformat()}"
    )
    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
        dispatch_error=final_wait_error,
    )
    db_session.add(todo)
    await db_session.flush()

    monkeypatch.setattr(verification, "schedule_todo_completion_verification", lambda *a, **kw: None)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=2,
    )

    assert todo.status == ProjectTodoStatus.blocked
    assert todo.blocked_reason is not None
    assert "incomplete" in todo.blocked_reason
    assert todo.dispatch_stage is None


@pytest.mark.asyncio
async def test_verification_bg_work_retry_increments_attempt(db_session, monkeypatch):
    """When the aux verification fails after waiting for background work, the
    retry must increment the attempt counter so the loop eventually terminates
    at max_attempts instead of looping forever (which spawns a new ephemeral
    verification window on every cycle - the tmux storm regression).

    Reproduces:
    - Todo waited for bg work (FINAL_COMPLETION_WAITING_PREFIX in dispatch_error)
    - Aux verification returns "incomplete" verdict
    - Pre-fix: reschedules with attempt=1 forever (storm)
    - Post-fix: reschedules with attempt+1, eventually blocks at max_attempts
    """
    from datetime import datetime, timezone
    from app.contexts.workspace.application.project_todo_background_completion import (
        FINAL_COMPLETION_WAITING_PREFIX,
    )

    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(False, [])),
    )
    monkeypatch.setattr(
        verification,
        "_run_verification_prompt",
        AsyncMock(return_value=verification.VerificationVerdict(
            verdict="incomplete",
            evidence="agent did not report final completion",
            open_processes=[],
        )),
    )

    todo_id = uuid4()
    completed_at = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    final_wait_error = (
        f"{FINAL_COMPLETION_WAITING_PREFIX}: last agent completion at "
        f"{completed_at.isoformat()}"
    )
    todo = ProjectTodo(
        id=todo_id,
        client_id=uuid4(),
        project_path="/tmp/proj",
        title="Background task",
        description="Start a background sleep and report back later.",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=uuid4(),
        dispatch_stage="verifying",
        dispatch_error=final_wait_error,
    )
    db_session.add(todo)
    await db_session.flush()

    scheduled_attempts: list[int] = []
    def fake_schedule(*args, **kwargs):
        scheduled_attempts.append(kwargs.get("attempt"))
        return None
    monkeypatch.setattr(verification, "schedule_todo_completion_verification", fake_schedule)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=todo.client_id,
        completed_at=completed_at,
        window_id=todo.assigned_window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    # The retry must increment the attempt counter instead of resetting it to 1.
    # Pre-fix bug: this was [1] (BACKGROUND_WORK_RECHECK_ATTEMPT), causing an
    # infinite loop that spawned a new verification window on every cycle.
    assert scheduled_attempts == [2], (
        f"retry must increment attempt (expected [2], got {scheduled_attempts}); "
        "resetting to 1 causes the tmux storm regression"
    )


class _CtxManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_verification_defers_when_async_subagent_still_pending(db_session, monkeypatch):
    """When the dispatched window still has pending async subagent work, the
    verification must defer completion (and reschedule a recheck) even if the
    pane itself has no active process.

    Reproduces the bug where Claude Code's Task tool launches an async
    subagent that runs `sleep 60`, the main agent then ends its turn (no
    active process in the pane), and the todo card was prematurely moved to
    review because verification only inspected pane processes.
    """
    todo_id = uuid4()
    client_id = uuid4()
    window_id = uuid4()

    db_session.add(Client(id=client_id, name="local", runtime=ClientRuntime.local, token_hash="hash", owner_user_id="owner"))
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Main agent terminal",
        status=WindowStatus.active,
        tmux_session="s",
        tmux_window_id="@1",
        agent_activity_pending_subagent_count=1,
    )
    db_session.add(window)
    completed_at = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    todo = ProjectTodo(
        id=todo_id,
        client_id=client_id,
        project_path="/tmp/proj",
        title="Delayed task",
        description="Launch a subagent that sleeps 60s; main agent exits early.",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window_id,
        dispatch_stage="verifying",
    )
    db_session.add(todo)
    await db_session.flush()

    async def fake_pane_has_active(*_args, **_kwargs):
        return False, []
    monkeypatch.setattr(
        verification,
        "pane_has_active_non_shell_process",
        fake_pane_has_active,
    )

    run_prompt = AsyncMock()
    monkeypatch.setattr(verification, "_run_verification_prompt", run_prompt)

    upgrade_called: list[bool] = []
    _patch_completion_upgrade(monkeypatch, upgrade_called)

    scheduled_calls: list[dict] = []
    def fake_schedule(*args, **kwargs):
        scheduled_calls.append(kwargs)
        return None
    monkeypatch.setattr(verification, "schedule_todo_completion_verification", fake_schedule)

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._verify_todo_completion(
        todo_id,
        client_id=client_id,
        completed_at=completed_at,
        window_id=window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
    )

    assert upgrade_called == []
    assert run_prompt.await_count == 0
    assert todo.status == ProjectTodoStatus.dispatched
    assert todo.dispatch_stage == "verifying"
    assert todo.dispatch_error is not None
    assert "pending subagent" in todo.dispatch_error
    assert len(scheduled_calls) == 1
    assert scheduled_calls[0]["delay_seconds"] > 0


@pytest.mark.asyncio
async def test_query_active_processes_reports_pending_subagent_count(db_session, monkeypatch):
    """_query_active_processes must surface pending subagent count as
    background-style active work so verification can defer completion.
    """
    client_id = uuid4()
    window_id = uuid4()

    db_session.add(Client(id=client_id, name="local", runtime=ClientRuntime.local, token_hash="hash", owner_user_id="owner"))
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Main agent terminal",
        status=WindowStatus.active,
        tmux_session="s",
        tmux_window_id="@1",
        agent_activity_pending_subagent_count=2,
    )
    db_session.add(window)
    await db_session.flush()

    async def fake_pane_has_active(*_args, **_kwargs):
        return False, []
    monkeypatch.setattr(
        verification,
        "pane_has_active_non_shell_process",
        fake_pane_has_active,
    )

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    has_active, active_processes = await verification._query_active_processes(
        client_id=client_id,
        window_id=window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
    )

    assert has_active is True
    assert any("pending subagent" in process for process in active_processes)
    assert "2" in active_processes[-1]


@pytest.mark.asyncio
async def test_delayed_verification_skips_when_another_is_in_progress(db_session, monkeypatch):
    """Concurrent completion events for the same window must not spawn multiple
    aux-agent ephemeral windows for the same todo. The per-todo reservation in
    _delayed_verify_todo_completion drops the duplicate run.

    Reproduces the tmux storm regression: multiple agent completion events
    arrive in quick succession, each calls schedule_todo_completion_verification,
    and without the reservation each task would create its own ephemeral window.
    """
    todo_id = uuid4()
    client_id = uuid4()
    window_id = uuid4()
    completed_at = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    # Hold the reservation manually to simulate another verification run that
    # is already in progress.
    assert verification._reserve_verification(todo_id) is True

    run_prompt = AsyncMock()
    monkeypatch.setattr(verification, "_run_verification_prompt", run_prompt)
    monkeypatch.setattr(
        verification,
        "_query_active_processes",
        AsyncMock(return_value=(True, ["sleep 120"])),
    )

    class FakeSessionFactory:
        def __call__(self):
            return _CtxManager(db_session)

    await verification._delayed_verify_todo_completion(
        todo_id,
        client_id=client_id,
        completed_at=completed_at,
        window_id=window_id,
        session_factory=FakeSessionFactory(),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        attempt=1,
        delay_seconds=0.0,
    )

    # The duplicate task must not call _run_verification_prompt at all.
    assert run_prompt.await_count == 0
    # Reservation must still be held by the manual caller; cleanup is theirs.
    assert todo_id in verification._verifications_in_progress
    verification._release_verification(todo_id)
