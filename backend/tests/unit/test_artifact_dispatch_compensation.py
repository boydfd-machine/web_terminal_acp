from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.terminal_artifacts.application import dispatch_compensation
from app.model_base import Base
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus


class FakeRuntime:
    pass


class FakeUiEventHub:
    pass


@pytest.mark.asyncio
async def test_process_artifact_dispatch_compensation_once_claims_and_schedules(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session_factory():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    async with AsyncSession(engine, expire_on_commit=False) as session:
        todo = ProjectTodo(
            id=uuid4(),
            client_id=uuid4(),
            project_path="/repo",
            title="Compensate artifact",
            status=ProjectTodoStatus.dispatched,
            assigned_window_id=uuid4(),
            artifact_kinds_json=["agent_trace_graph"],
        )
        artifact = TerminalArtifact(
            id=uuid4(),
            client_id=todo.client_id,
            virtual_window_id=todo.assigned_window_id,
            source_window_id=todo.assigned_window_id,
            artifact_kind="agent_trace_graph",
            title="Trace",
            status=TerminalArtifactStatus.pending,
            metadata_json={
                "project_todo_id": str(todo.id),
                "purpose": "todo_artifact",
                "artifact_scope": "terminal",
            },
        )
        session.add_all([todo, artifact])
        await session.flush()
        session.add(
            ProjectTodoArtifact(
                project_todo_id=todo.id,
                terminal_artifact_id=artifact.id,
                created_by_window_id=todo.assigned_window_id,
                purpose="todo_artifact",
            )
        )
        await session.commit()

    scheduled = []

    def fake_schedule_project_todo_requested_artifacts(generations, runtime):
        scheduled.extend(generations)

    monkeypatch.setattr(
        dispatch_compensation,
        "schedule_project_todo_requested_artifacts",
        fake_schedule_project_todo_requested_artifacts,
    )

    processed = await dispatch_compensation.process_artifact_dispatch_compensation_once(
        session_factory,
        tmux_manager=FakeRuntime(),
        terminal_broker=FakeRuntime(),
        registry=FakeRuntime(),
        ui_event_hub=FakeUiEventHub(),
    )

    assert processed == 1
    assert len(scheduled) == 1
    assert scheduled[0].artifact_id == artifact.id
    async with AsyncSession(engine, expire_on_commit=False) as session:
        stored = await session.get(TerminalArtifact, artifact.id)
    assert stored is not None
    assert stored.metadata_json["dispatch_attempted_at"]

    await engine.dispose()
