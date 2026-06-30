from __future__ import annotations

from uuid import uuid4

import pytest

from app.contexts.terminal_runtime.application.agent_task_runner import AgentTaskResult
from app.contexts.workspace.application import project_todo_completion_aux_agent as aux_agent
from app.models import ProjectTodo


@pytest.mark.asyncio
async def test_run_verification_prompt_uses_unique_output_path(monkeypatch) -> None:
    todo = ProjectTodo(id=uuid4(), title="Delayed task", description="Wait for a timer")
    session = _Session(todo)
    captured_specs = []

    async def fake_run_agent_task(_session, spec, **_kwargs):
        captured_specs.append(spec)
        return AgentTaskResult(
            output='{"verdict":"complete","evidence":"done","open_processes":[]}',
            ephemeral_window_id=uuid4(),
            started_at=None,
            finished_at=None,
        )

    monkeypatch.setattr(aux_agent, "run_agent_task", fake_run_agent_task)

    for _ in range(2):
        verdict = await aux_agent.run_verification_prompt(
            todo_id=todo.id,
            client_id=uuid4(),
            window_id=uuid4(),
            attempt=1,
            active_processes=[],
            session_factory=lambda: _Ctx(session),
            tmux_manager=object(),
            terminal_broker=None,
            registry=None,
            waited_for_background_work=True,
        )
        assert verdict.verdict == "complete"

    output_paths = [spec.output_path for spec in captured_specs]
    assert output_paths[0] != output_paths[1]
    for spec in captured_specs:
        assert spec.output_path is not None
        assert spec.output_path in spec.prompt
        assert spec.output_path.startswith(f"/tmp/web-terminal-todo-verification-{todo.id}-1-")


@pytest.mark.asyncio
async def test_run_verification_prompt_passes_active_session_to_run_agent_task(monkeypatch) -> None:
    """The session handed to run_agent_task must still be open.

    Closing the session before run_agent_task runs leaves the underlying
    AsyncSession facade pointing at a closed transaction; SQLAlchemy then
    re-checks out connections that never get checked back in, which is what
    produces the QueuePool exhaustion we saw in production logs.
    """
    todo = ProjectTodo(id=uuid4(), title="Delayed task", description="Wait for a timer")
    session = _Session(todo)
    session_states: list[bool] = []

    async def fake_run_agent_task(passed_session, spec, **_kwargs):
        session_states.append(passed_session.is_closed)
        return AgentTaskResult(
            output='{"verdict":"complete","evidence":"done","open_processes":[]}',
            ephemeral_window_id=uuid4(),
            started_at=None,
            finished_at=None,
        )

    monkeypatch.setattr(aux_agent, "run_agent_task", fake_run_agent_task)

    await aux_agent.run_verification_prompt(
        todo_id=todo.id,
        client_id=uuid4(),
        window_id=uuid4(),
        attempt=1,
        active_processes=[],
        session_factory=lambda: _Ctx(session),
        tmux_manager=object(),
        terminal_broker=None,
        registry=None,
        waited_for_background_work=True,
    )

    assert session_states == [False]


class _Session:
    def __init__(self, todo: ProjectTodo) -> None:
        self._todo = todo
        self.is_closed = False

    async def get(self, model, object_id):
        assert model is ProjectTodo
        assert object_id == self._todo.id
        return self._todo


class _Ctx:
    def __init__(self, session: _Session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        self._session.is_closed = True
        return False
