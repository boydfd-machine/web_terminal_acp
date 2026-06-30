from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tests.unit.test_summary_scheduler_support import db_session  # noqa: F401

from app.contexts.workspace.application import project_todo_artifact_scheduler as artifact_scheduler
from app.contexts.workspace.application.project_todo_artifacts import ProjectTodoArtifactGeneration
from app.models import ProjectTodo, ProjectTodoStatus


@pytest.mark.asyncio
async def test_complete_project_todo_implementation_schedules_created_requested_artifacts(
    db_session,
    monkeypatch,
):
    client_id = uuid4()
    window_id = uuid4()
    generation = ProjectTodoArtifactGeneration(
        client_id=client_id,
        window_id=window_id,
        artifact_id=uuid4(),
        prompt="Generate the requested review artifact.",
        output_language="English",
    )

    async def fake_mark_completed(*args, **kwargs):
        return [generation]

    scheduled = []

    def fake_schedule_project_todo_artifact_generations(generations):
        scheduled.extend(generations)

    monkeypatch.setattr(artifact_scheduler, "_mark_implementation_completed", fake_mark_completed)
    monkeypatch.setattr(
        artifact_scheduler,
        "schedule_project_todo_artifact_generations",
        fake_schedule_project_todo_artifact_generations,
    )

    todo = ProjectTodo(
        id=uuid4(),
        client_id=client_id,
        project_path="/tmp/proj",
        title="Task",
        status=ProjectTodoStatus.dispatched,
        assigned_window_id=window_id,
        dispatch_stage="verifying",
    )
    db_session.add(todo)
    await db_session.flush()

    await artifact_scheduler.complete_project_todo_implementation(
        db_session,
        todo,
        completed_at=datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc),
        window_id=window_id,
        remote_client_available=None,
    )

    assert scheduled == [generation]
    assert todo.dispatch_stage is None
