from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.terminal_artifacts.application.project_incremental import (
    build_project_artifact_workspace,
)
from app.contexts.workspace.application import project_todo_artifacts
from app.contexts.workspace.infrastructure import project_todo_list_queries
from app.contexts.workspace.infrastructure import project_todos_repository
from app.model_base import Base
from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus
from app.platform.plugins.artifact_plugins.acas_project_artifacts import (
    AcasProjectArtifactPlugin,
    AcasProjectArtifactSpec,
)
from app.platform.plugins.artifact_plugins.agent_trace_graph import AgentTraceGraphArtifactPlugin


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


def test_requested_project_user_journey_artifact_prompt_includes_todo_context() -> None:
    todo = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="user journey生成",
        description="生成本项目的user journey",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=1,
        assigned_window_id=uuid4(),
        artifact_kinds_json=["page_review_cards", "project:user_journey"],
        dispatch_prompt="Clarify the target user and current journey.",
    )
    artifact_ref = project_todo_artifacts.ProjectTodoArtifactKindRef(
        scope="project",
        kind="user_journey",
    )
    plugin = _project_artifact_plugin("user_journey")

    draft = project_todo_artifacts._project_todo_artifact_draft(todo, artifact_ref, plugin)

    assert draft.prompt is not None
    assert "user journey生成" in draft.prompt
    assert "生成本项目的user journey" in draft.prompt
    assert "project:user_journey" in draft.prompt
    assert "Clarify the target user and current journey." in draft.prompt


def test_requested_artifact_draft_uses_todo_preferred_output_language() -> None:
    todo = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="生成 trace",
        description="用中文生成 artifact",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=1,
        assigned_window_id=uuid4(),
        artifact_kinds_json=["agent_trace_graph"],
        dispatch_prompt="实现并验证这个卡片",
        dispatch_output_language="中文",
    )
    artifact_ref = project_todo_artifacts.ProjectTodoArtifactKindRef(
        scope="terminal",
        kind="agent_trace_graph",
    )
    plugin = _terminal_artifact_plugin("agent_trace_graph")

    draft = project_todo_artifacts._project_todo_artifact_draft(todo, artifact_ref, plugin)

    assert draft.prompt is not None
    assert "Generate the requested artifact for this project todo." in draft.prompt
    assert draft.output_language == "中文"
    assert draft.metadata_json["output_language"] == "中文"


def test_fresh_project_user_journey_workspace_starts_from_acas_raw_context() -> None:
    plugin = _project_artifact_plugin("user_journey")

    workspace = build_project_artifact_workspace(
        uuid4(),
        None,
        plugin,
        initial_context={
            "todo_title": "user journey生成",
            "todo_description": "生成本项目的user journey",
            "source_title": "用户旅程",
        },
    )

    assert workspace.content_json["kind"] == "UserJourneyRaw"
    assert workspace.content_json["layer"] == "Raw"
    assert "artifact_kind" not in workspace.content_json
    raw_content = workspace.content_json["rawInputs"][0]["content"]
    assert "user journey生成" in raw_content
    assert "生成本项目的user journey" in raw_content
    parsed = plugin.parse_output(json.dumps(workspace.content_json, ensure_ascii=False))
    assert parsed["kind"] == "UserJourneyRaw"


@pytest.mark.asyncio
async def test_create_missing_artifacts_does_not_lock_obvious_non_candidates(monkeypatch) -> None:
    locked_ids = []

    async def fail_if_locked(_session, todo_id, *, include_dispatched):
        locked_ids.append((todo_id, include_dispatched))
        raise AssertionError("non-candidate todo should not be locked")

    monkeypatch.setattr(
        project_todo_artifacts,
        "_locked_project_todo_for_artifact_generation",
        fail_if_locked,
    )

    no_artifact_request = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="No requested artifact",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=1,
        assigned_window_id=uuid4(),
        artifact_kinds_json=None,
    )
    no_window = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="No implementation window",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=2,
        assigned_window_id=None,
        artifact_kinds_json=["agent_trace_graph"],
    )
    dispatched_without_include = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="Still dispatched",
        status=ProjectTodoStatus.dispatched,
        sort_order=3,
        assigned_window_id=uuid4(),
        artifact_kinds_json=["agent_trace_graph"],
    )

    generations = await project_todo_artifacts.create_missing_project_todo_requested_artifacts(
        object(),
        [no_artifact_request, no_window, dispatched_without_include],
    )

    assert generations == []
    assert locked_ids == []


@pytest.mark.asyncio
async def test_create_missing_artifacts_skips_locked_candidate(monkeypatch) -> None:
    candidate = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="Ready for artifact",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=1,
        assigned_window_id=uuid4(),
        artifact_kinds_json=["agent_trace_graph"],
    )
    locked_ids = []

    async def skip_locked(_session, todo_id, *, include_dispatched):
        locked_ids.append((todo_id, include_dispatched))
        return None

    monkeypatch.setattr(
        project_todo_artifacts,
        "_locked_project_todo_for_artifact_generation",
        skip_locked,
    )
    monkeypatch.setattr(project_todo_artifacts, "_linked_requested_artifacts_for_todos", _no_linked_artifacts)

    generations = await project_todo_artifacts.create_missing_project_todo_requested_artifacts(
        object(),
        [candidate],
    )

    assert generations == []
    assert locked_ids == [(candidate.id, False)]


async def _no_linked_artifacts(_session, _todo_ids, *, purpose):
    return {}


@pytest.mark.asyncio
async def test_create_missing_artifacts_loads_existing_requested_artifacts_in_batches(monkeypatch) -> None:
    candidates = [
        ProjectTodo(
            id=uuid4(),
            client_id=uuid4(),
            project_path="/repo",
            title=f"Ready for artifact {index}",
            status=ProjectTodoStatus.awaiting_review,
            sort_order=index,
            assigned_window_id=uuid4(),
            artifact_kinds_json=["agent_trace_graph"],
        )
        for index in range(3)
    ]
    locked_ids = []
    batch_calls = []

    async def locked_todo(_session, todo_id, *, include_dispatched):
        locked_ids.append((todo_id, include_dispatched))
        return next(todo for todo in candidates if todo.id == todo_id)

    async def can_create(_session, _todo, *, include_dispatched, remote_client_available):
        return True

    async def existing_artifacts(_session, todo_ids, *, purpose):
        batch_calls.append(list(todo_ids))
        return {}

    async def create_artifact(_session, todo, encoded_kind):
        return project_todo_artifacts.ProjectTodoArtifactGeneration(
            client_id=todo.client_id,
            window_id=todo.assigned_window_id,
            artifact_id=uuid4(),
            prompt=f"create {encoded_kind}",
            output_language=None,
        )

    monkeypatch.setattr(
        project_todo_artifacts,
        "_locked_project_todo_for_artifact_generation",
        locked_todo,
    )
    monkeypatch.setattr(project_todo_artifacts, "_todo_can_create_requested_artifacts", can_create)
    monkeypatch.setattr(project_todo_artifacts, "_linked_requested_artifacts_for_todos", existing_artifacts)
    monkeypatch.setattr(project_todo_artifacts, "_create_project_todo_artifact", create_artifact)

    generations = await project_todo_artifacts.create_missing_project_todo_requested_artifacts(
        object(),
        candidates,
    )

    assert len(generations) == 3
    assert locked_ids == [(todo.id, False) for todo in candidates]
    assert batch_calls == [
        [todo.id for todo in candidates],
        [todo.id for todo in candidates],
    ]


@pytest.mark.asyncio
async def test_create_missing_artifacts_does_not_lock_fully_satisfied_candidates(monkeypatch) -> None:
    candidate = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="Already has requested artifact",
        status=ProjectTodoStatus.awaiting_review,
        sort_order=1,
        assigned_window_id=uuid4(),
        artifact_kinds_json=["agent_trace_graph"],
    )
    batch_calls = []

    async def fail_if_locked(*args, **kwargs):
        raise AssertionError("fully satisfied candidate should not be locked")

    async def existing_artifacts(_session, todo_ids, *, purpose):
        batch_calls.append(list(todo_ids))
        return {candidate.id: ({"agent_trace_graph"}, {})}

    async def fail_if_created(*args, **kwargs):
        raise AssertionError("fully satisfied candidate should not create artifacts")

    monkeypatch.setattr(
        project_todo_artifacts,
        "_locked_project_todo_for_artifact_generation",
        fail_if_locked,
    )
    monkeypatch.setattr(project_todo_artifacts, "_linked_requested_artifacts_for_todos", existing_artifacts)
    monkeypatch.setattr(project_todo_artifacts, "_create_project_todo_artifact", fail_if_created)

    generations = await project_todo_artifacts.create_missing_project_todo_requested_artifacts(
        object(),
        [candidate],
    )

    assert generations == []
    assert batch_calls == [[candidate.id]]


@pytest.mark.asyncio
async def test_artifact_generation_lock_query_skips_locked_candidates() -> None:
    class CaptureSession:
        statement = None

        async def scalar(self, statement):
            self.statement = statement
            return None

    session = CaptureSession()

    await project_todo_artifacts._locked_project_todo_for_artifact_generation(
        session,
        uuid4(),
        include_dispatched=True,
    )

    compiled = str(session.statement.compile(dialect=postgresql.dialect()))

    assert "project_todos.artifact_kinds_json IS NOT NULL" in compiled
    assert "project_todos.assigned_window_id IS NOT NULL" in compiled
    assert "project_todos.status IN" in compiled
    assert "FOR UPDATE SKIP LOCKED" in compiled


@pytest.mark.asyncio
async def test_list_project_todo_artifact_candidates_query_prefilters_ready_rows() -> None:
    class CaptureSession:
        statement = None

        async def scalars(self, statement):
            self.statement = statement
            return []

    session = CaptureSession()

    await project_todo_list_queries.list_project_todo_artifact_candidates(
        session,
        uuid4(),
        "/repo",
    )

    compiled = str(session.statement.compile(dialect=postgresql.dialect()))

    assert "project_todos.artifact_kinds_json IS NOT NULL" in compiled
    assert "project_todos.assigned_window_id IS NOT NULL" in compiled
    assert "project_todos.status IN" in compiled
    assert "project_todos.updated_at >=" not in compiled


@pytest.mark.asyncio
async def test_project_todo_artifact_list_query_omits_large_artifact_payload_columns() -> None:
    class CaptureSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return []

    session = CaptureSession()

    await project_todos_repository.list_project_todo_artifacts(
        session,
        [uuid4()],
    )

    compiled = str(session.statement.compile(dialect=postgresql.dialect()))

    assert "terminal_artifacts.content_json" not in compiled
    assert "terminal_artifacts.display_html" not in compiled
    assert "terminal_artifacts.metadata_json" in compiled


@pytest.mark.asyncio
async def test_compensation_schedules_unattempted_pending_project_todo_artifact(db_session) -> None:
    todo = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="Ready for artifact compensation",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
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
    db_session.add_all([todo, artifact])
    await db_session.flush()
    db_session.add(
        ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=todo.assigned_window_id,
            purpose="todo_artifact",
        )
    )
    await db_session.flush()

    generations = await project_todo_artifacts.claim_pending_project_todo_artifact_generations(db_session)

    assert len(generations) == 1
    assert generations[0].client_id == todo.client_id
    assert generations[0].window_id == todo.assigned_window_id
    assert generations[0].artifact_id == artifact.id
    assert artifact.metadata_json["dispatch_attempted_at"]


@pytest.mark.asyncio
async def test_compensation_skips_recent_dispatch_attempt_and_retries_stale_pending_artifact(db_session) -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    todo = ProjectTodo(
        id=uuid4(),
        client_id=uuid4(),
        project_path="/repo",
        title="Already attempted",
        status=ProjectTodoStatus.dispatched,
        sort_order=1,
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
            "dispatch_attempted_at": now.isoformat(),
        },
    )
    db_session.add_all([todo, artifact])
    await db_session.flush()
    db_session.add(
        ProjectTodoArtifact(
            project_todo_id=todo.id,
            terminal_artifact_id=artifact.id,
            created_by_window_id=todo.assigned_window_id,
            purpose="todo_artifact",
        )
    )
    await db_session.flush()

    generations = await project_todo_artifacts.claim_pending_project_todo_artifact_generations(
        db_session,
        now=now + timedelta(seconds=5),
        retry_after_seconds=30,
    )

    assert generations == []

    retry_generations = await project_todo_artifacts.claim_pending_project_todo_artifact_generations(
        db_session,
        now=now + timedelta(seconds=31),
        retry_after_seconds=30,
    )

    assert len(retry_generations) == 1
    assert retry_generations[0].artifact_id == artifact.id


def _project_artifact_plugin(artifact_kind: str):
    if artifact_kind != "user_journey":
        raise ValueError(f"unsupported ACAS project artifact kind: {artifact_kind}")
    return AcasProjectArtifactPlugin(
        AcasProjectArtifactSpec(
            artifact_kind="user_journey",
            label="User Journey",
            default_title="Project user journey",
            acas_definition_id="user-journey",
            current_kind="UserJourneyCurrent",
            renderer_name="user-journey-renderer.html",
            methodology_skill="user-journey-methodology",
            summary="single reviewed user journey source truth",
        )
    )


def _terminal_artifact_plugin(artifact_kind: str):
    if artifact_kind != "agent_trace_graph":
        raise ValueError(f"unsupported terminal artifact kind: {artifact_kind}")
    return AgentTraceGraphArtifactPlugin()
