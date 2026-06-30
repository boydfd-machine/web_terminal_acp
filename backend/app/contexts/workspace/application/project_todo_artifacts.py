from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.contexts.terminal_artifacts.application import TerminalArtifactGenerationRequest
from app.contexts.terminal_artifacts.application.artifact_creation import create_terminal_artifact_record
from app.contexts.terminal_artifacts.application.model_selection import (
    ARTIFACT_MODEL_SELECTION_METADATA_KEY,
)
from app.contexts.terminal_artifacts.domain import TerminalArtifactDraft
from app.contexts.workspace.application import project_todo_artifact_prompt as artifact_prompt
from app.contexts.workspace.application.project_todo_prompt_references import single_line_output_language
from app.contexts.workspace.application.project_todo_requested_artifacts import (
    linked_requested_artifacts_for_todos as _linked_requested_artifacts_for_todos,
)
from app.models import (
    Client,
    ClientRuntime,
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoStatus,
    TerminalArtifact,
    TerminalArtifactStatus,
)
from app.platform.plugins.artifact_plugins import get_artifact_plugin_registry_for_scope
from app.platform.plugins.artifact_plugins.user_settings_repository import (
    restore_artifact_plugin_files_to_disk,
)

if TYPE_CHECKING:
    from app.contexts.terminal_artifacts.application.api_service import TerminalArtifactRuntimeDeps

PROJECT_TODO_ARTIFACT_PURPOSE = "todo_artifact"
PROJECT_ARTIFACT_PREFIX = "project:"
PROJECT_TODO_ARTIFACT_GENERATIONS_SESSION_KEY = "project_todo_artifact_generations"
ARTIFACT_DISPATCH_ATTEMPTED_METADATA_KEY = "dispatch_attempted_at"
ARTIFACT_DISPATCH_RETRY_AFTER_SECONDS = 30.0


@dataclass(frozen=True)
class ProjectTodoArtifactGeneration:
    client_id: UUID
    window_id: UUID
    artifact_id: UUID
    prompt: str | None
    output_language: str | None

@dataclass(frozen=True)
class ProjectTodoArtifactKindRef:
    scope: str
    kind: str
    @property
    def encoded(self) -> str:
        return f"{PROJECT_ARTIFACT_PREFIX}{self.kind}" if self.scope == "project" else self.kind


def normalize_project_todo_artifact_kinds(artifact_kinds: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_kind in artifact_kinds or []:
        artifact_ref = _artifact_kind_ref(raw_kind)
        if artifact_ref is None:
            continue
        plugin = get_artifact_plugin_registry_for_scope(artifact_ref.scope).by_kind(artifact_ref.kind)
        canonical = ProjectTodoArtifactKindRef(scope=artifact_ref.scope, kind=plugin.artifact_kind).encoded
        key = canonical.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(canonical)
    return normalized


async def create_missing_project_todo_requested_artifacts(
    session: AsyncSession,
    todos: list[ProjectTodo],
    *,
    include_dispatched: bool = False,
    remote_client_available: Callable[[UUID], bool] | None = None,
) -> list[ProjectTodoArtifactGeneration]:
    generations: list[ProjectTodoArtifactGeneration] = []
    candidates = [
        todo
        for todo in todos
        if _project_todo_may_create_requested_artifacts(
            todo,
            include_dispatched=include_dispatched,
        )
    ]
    preloaded_artifacts = await _linked_requested_artifacts_for_todos(
        session,
        [todo.id for todo in candidates],
        purpose=PROJECT_TODO_ARTIFACT_PURPOSE,
    )
    locked_todos: list[ProjectTodo] = []
    for unlocked_todo in candidates:
        existing_kinds, retryable_artifacts = preloaded_artifacts.get(unlocked_todo.id, (set(), {}))
        if not _todo_needs_requested_artifact_generation(unlocked_todo, existing_kinds, retryable_artifacts):
            continue
        todo = await _locked_project_todo_for_artifact_generation(
            session,
            unlocked_todo.id,
            include_dispatched=include_dispatched,
        )
        if todo is None:
            continue
        if not await _todo_can_create_requested_artifacts(
            session,
            todo,
            include_dispatched=include_dispatched,
            remote_client_available=remote_client_available,
        ):
            continue
        locked_todos.append(todo)
    if not locked_todos:
        return generations
    confirmed_artifacts = await _linked_requested_artifacts_for_todos(
        session,
        [todo.id for todo in locked_todos],
        purpose=PROJECT_TODO_ARTIFACT_PURPOSE,
    )
    for todo in locked_todos:
        existing_kinds, retryable_artifacts = confirmed_artifacts.get(todo.id, (set(), {}))
        for encoded_kind in normalize_project_todo_artifact_kinds(todo.artifact_kinds_json):
            if encoded_kind in existing_kinds:
                continue
            retryable_artifact = retryable_artifacts.get(encoded_kind)
            generation = (
                await _retry_project_todo_artifact(session, todo, retryable_artifact, encoded_kind)
                if retryable_artifact is not None
                else await _create_project_todo_artifact(session, todo, encoded_kind)
            )
            generations.append(generation)
            existing_kinds.add(encoded_kind)
    return generations


def queue_project_todo_artifact_generations(
    session: AsyncSession,
    generations: list[ProjectTodoArtifactGeneration],
) -> None:
    if not generations:
        return
    queued = session.info.setdefault(PROJECT_TODO_ARTIFACT_GENERATIONS_SESSION_KEY, [])
    queued.extend(generations)


def pop_project_todo_artifact_generations(
    session: AsyncSession,
) -> list[ProjectTodoArtifactGeneration]:
    return list(session.info.pop(PROJECT_TODO_ARTIFACT_GENERATIONS_SESSION_KEY, []))


def schedule_project_todo_requested_artifacts(
    generations: list[ProjectTodoArtifactGeneration],
    runtime: TerminalArtifactRuntimeDeps,
) -> None:
    for generation in generations:
        runtime.schedule_generation(
            TerminalArtifactGenerationRequest(
                client_id=generation.client_id,
                window_id=generation.window_id,
                artifact_id=generation.artifact_id,
                prompt=generation.prompt,
                output_language=generation.output_language,
            ),
            session_factory=runtime.session_factory,
            tmux_manager=runtime.tmux_manager,
            terminal_broker=runtime.terminal_broker,
            registry=runtime.registry,
            ui_event_hub=runtime.ui_event_hub,
        )


async def claim_pending_project_todo_artifact_generations(
    session: AsyncSession,
    *,
    limit: int = 25,
    now: datetime | None = None,
    retry_after_seconds: float = ARTIFACT_DISPATCH_RETRY_AFTER_SECONDS,
) -> list[ProjectTodoArtifactGeneration]:
    current_time = _ensure_aware(now or datetime.now(UTC))
    rows = await session.execute(
        select(ProjectTodo, TerminalArtifact)
        .join(ProjectTodoArtifact, ProjectTodoArtifact.project_todo_id == ProjectTodo.id)
        .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
        .where(
            ProjectTodoArtifact.purpose == PROJECT_TODO_ARTIFACT_PURPOSE,
            TerminalArtifact.status == TerminalArtifactStatus.pending,
        )
        .order_by(TerminalArtifact.created_at, TerminalArtifact.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    generations: list[ProjectTodoArtifactGeneration] = []
    for todo, artifact in rows:
        if not _artifact_dispatch_is_retryable(
            artifact,
            now=current_time,
            retry_after_seconds=retry_after_seconds,
        ):
            continue
        if not _project_todo_may_create_requested_artifacts(todo, include_dispatched=True):
            continue
        encoded_kind = ProjectTodoArtifactKindRef(
            scope=artifact.artifact_scope or "terminal",
            kind=artifact.artifact_kind,
        ).encoded
        if encoded_kind not in normalize_project_todo_artifact_kinds(todo.artifact_kinds_json):
            continue
        _mark_artifact_dispatch_attempted(artifact, now=current_time)
        generations.append(
            ProjectTodoArtifactGeneration(
                client_id=artifact.client_id,
                window_id=artifact.virtual_window_id,
                artifact_id=artifact.id,
                prompt=None,
                output_language=_artifact_output_language(artifact),
            )
        )
    if generations:
        await session.flush()
    return generations


async def retry_failed_project_todo_artifact(
    session: AsyncSession,
    todo: ProjectTodo,
    link_id: UUID,
) -> ProjectTodoArtifactGeneration:
    link, artifact = await _locked_project_todo_artifact_link(session, todo.id, link_id)
    if link.purpose != PROJECT_TODO_ARTIFACT_PURPOSE:
        raise ValueError("artifact is not a requested todo artifact")
    if artifact.status is not TerminalArtifactStatus.failed:
        raise ValueError("artifact is not failed")
    encoded_kind = ProjectTodoArtifactKindRef(
        scope=artifact.artifact_scope or "terminal",
        kind=artifact.artifact_kind,
    ).encoded
    if encoded_kind not in normalize_project_todo_artifact_kinds(todo.artifact_kinds_json):
        raise ValueError("artifact is no longer requested")
    if not await _todo_can_create_requested_artifacts(
        session,
        todo,
        include_dispatched=True,
        remote_client_available=None,
    ):
        raise ValueError("todo is not ready for artifact retry")
    return await _retry_project_todo_artifact(session, todo, artifact, encoded_kind)


async def _locked_project_todo_artifact_link(
    session: AsyncSession,
    todo_id: UUID,
    link_id: UUID,
) -> tuple[ProjectTodoArtifact, TerminalArtifact]:
    row = (
        await session.execute(
            select(ProjectTodoArtifact, TerminalArtifact)
            .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
            .where(
                ProjectTodoArtifact.id == link_id,
                ProjectTodoArtifact.project_todo_id == todo_id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise LookupError("artifact link not found")
    link, artifact = row
    return link, artifact


async def _locked_project_todo_for_artifact_generation(
    session: AsyncSession,
    todo_id: UUID,
    *,
    include_dispatched: bool,
) -> ProjectTodo | None:
    ready_statuses = [ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done]
    if include_dispatched:
        ready_statuses.append(ProjectTodoStatus.dispatched)
    return await session.scalar(
        select(ProjectTodo)
        .where(
            ProjectTodo.id == todo_id,
            ProjectTodo.artifact_kinds_json.is_not(None),
            ProjectTodo.assigned_window_id.is_not(None),
            ProjectTodo.status.in_(ready_statuses),
        )
        .with_for_update(skip_locked=True)
    )


def _project_todo_may_create_requested_artifacts(
    todo: ProjectTodo,
    *,
    include_dispatched: bool,
) -> bool:
    ready_statuses = {ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done}
    if include_dispatched:
        ready_statuses.add(ProjectTodoStatus.dispatched)
    return bool(todo.artifact_kinds_json) and todo.assigned_window_id is not None and todo.status in ready_statuses


def _todo_needs_requested_artifact_generation(
    todo: ProjectTodo,
    existing_kinds: set[str],
    retryable_artifacts: dict[str, TerminalArtifact],
) -> bool:
    for encoded_kind in normalize_project_todo_artifact_kinds(todo.artifact_kinds_json):
        if encoded_kind not in existing_kinds or encoded_kind in retryable_artifacts:
            return True
    return False


async def _todo_can_create_requested_artifacts(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    include_dispatched: bool,
    remote_client_available: Callable[[UUID], bool] | None,
) -> bool:
    ready_statuses = {ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done}
    if include_dispatched:
        ready_statuses.add(ProjectTodoStatus.dispatched)
    if not _project_todo_may_create_requested_artifacts(todo, include_dispatched=include_dispatched):
        return False
    if remote_client_available is None:
        return True
    client = await session.get(Client, todo.client_id)
    if client is None:
        return False
    return client.runtime is not ClientRuntime.remote or remote_client_available(todo.client_id)


async def _create_project_todo_artifact(
    session: AsyncSession,
    todo: ProjectTodo,
    encoded_kind: str,
) -> ProjectTodoArtifactGeneration:
    artifact_ref = _artifact_kind_ref(encoded_kind)
    if artifact_ref is None:
        raise ValueError("artifact kind is required")
    plugin = await _artifact_plugin_for_todo(session, todo, artifact_ref)
    draft = _project_todo_artifact_draft(todo, artifact_ref, plugin)
    artifact = await create_terminal_artifact_record(
        session,
        client_id=todo.client_id,
        virtual_window_id=todo.assigned_window_id,
        source_window_id=todo.assigned_window_id,
        artifact_scope=artifact_ref.scope,
        project_path=todo.project_path if artifact_ref.scope == "project" else None,
        artifact_kind=draft.artifact_kind,
        title=draft.title,
        metadata_json=draft.metadata_json,
    )
    from app.contexts.workspace.infrastructure.project_todos_repository import link_project_todo_artifact

    await link_project_todo_artifact(
        session,
        todo,
        artifact.id,
        purpose=PROJECT_TODO_ARTIFACT_PURPOSE,
    )
    _mark_artifact_dispatch_attempted(artifact)
    await session.flush()
    return ProjectTodoArtifactGeneration(
        client_id=todo.client_id,
        window_id=todo.assigned_window_id,
        artifact_id=artifact.id,
        prompt=draft.prompt,
        output_language=draft.output_language,
    )


async def _retry_project_todo_artifact(
    session: AsyncSession,
    todo: ProjectTodo,
    artifact: TerminalArtifact,
    encoded_kind: str,
) -> ProjectTodoArtifactGeneration:
    artifact_ref = _artifact_kind_ref(encoded_kind)
    if artifact_ref is None:
        raise ValueError("artifact kind is required")
    plugin = await _artifact_plugin_for_todo(session, todo, artifact_ref)
    draft = _project_todo_artifact_draft(todo, artifact_ref, plugin)
    artifact.virtual_window_id = todo.assigned_window_id
    artifact.source_window_id = todo.assigned_window_id
    artifact.ephemeral_window_id = None
    artifact.artifact_scope = artifact_ref.scope
    artifact.project_path = todo.project_path if artifact_ref.scope == "project" else None
    artifact.artifact_kind = draft.artifact_kind
    artifact.title = draft.title
    artifact.status = TerminalArtifactStatus.pending
    artifact.content_json = None
    artifact.display_html = None
    artifact.metadata_json = draft.metadata_json
    artifact.last_error = None
    artifact.started_at = None
    artifact.completed_at = None
    _mark_artifact_dispatch_attempted(artifact)
    await session.flush()
    return ProjectTodoArtifactGeneration(
        client_id=todo.client_id,
        window_id=todo.assigned_window_id,
        artifact_id=artifact.id,
        prompt=draft.prompt,
        output_language=draft.output_language,
    )


async def _artifact_plugin_for_todo(
    session: AsyncSession,
    todo: ProjectTodo,
    artifact_ref: ProjectTodoArtifactKindRef,
):
    client = await session.get(Client, todo.client_id)
    owner_user_id = client.owner_user_id if client is not None else None
    await restore_artifact_plugin_files_to_disk(session, owner_user_id=owner_user_id)
    return get_artifact_plugin_registry_for_scope(
        artifact_ref.scope,
        owner_user_id=owner_user_id,
    ).by_kind(artifact_ref.kind)


def _project_todo_artifact_draft(
    todo: ProjectTodo,
    artifact_ref: ProjectTodoArtifactKindRef,
    plugin: object,
) -> TerminalArtifactDraft:
    output_language = single_line_output_language(todo.dispatch_output_language) or get_settings().summary_output_language
    payload = SimpleNamespace(
        artifact_kind=plugin.artifact_kind,
        title=f"{todo.title} - {plugin.label}",
        prompt=artifact_prompt.build_requested_artifact_prompt(todo, artifact_ref.encoded),
        output_language=output_language,
        metadata_json={
            "project_todo_id": str(todo.id),
            "purpose": PROJECT_TODO_ARTIFACT_PURPOSE,
            "artifact_scope": artifact_ref.scope,
            "project_path": todo.project_path if artifact_ref.scope == "project" else None,
            **artifact_prompt.requested_artifact_context_metadata(todo, artifact_ref.encoded),
            **_artifact_model_selection_metadata(todo),
        },
        terminal_retention_seconds=None,
    )
    return TerminalArtifactDraft.from_payload(
        payload,
        plugin=plugin,
        default_retention_seconds=get_settings().terminal_artifact_terminal_retention_seconds,
    )


def _artifact_model_selection_metadata(todo: ProjectTodo) -> dict[str, Any]:
    selection = todo.artifact_model_selection_json
    return {ARTIFACT_MODEL_SELECTION_METADATA_KEY: selection} if isinstance(selection, dict) else {}


def _artifact_kind_ref(raw_kind: str | None) -> ProjectTodoArtifactKindRef | None:
    kind = (raw_kind or "").strip()
    if not kind:
        return None
    if kind.lower().startswith(PROJECT_ARTIFACT_PREFIX):
        return ProjectTodoArtifactKindRef(scope="project", kind=kind[len(PROJECT_ARTIFACT_PREFIX):].strip())
    return ProjectTodoArtifactKindRef(scope="terminal", kind=kind)


def _mark_artifact_dispatch_attempted(
    artifact: TerminalArtifact,
    *,
    now: datetime | None = None,
) -> None:
    metadata = dict(artifact.metadata_json or {})
    metadata[ARTIFACT_DISPATCH_ATTEMPTED_METADATA_KEY] = _ensure_aware(now or datetime.now(UTC)).isoformat()
    artifact.metadata_json = metadata


def _artifact_dispatch_is_retryable(
    artifact: TerminalArtifact,
    *,
    now: datetime,
    retry_after_seconds: float,
) -> bool:
    metadata = artifact.metadata_json if isinstance(artifact.metadata_json, dict) else {}
    attempted_at = _datetime_metadata_value(metadata.get(ARTIFACT_DISPATCH_ATTEMPTED_METADATA_KEY))
    if attempted_at is None:
        return True
    return _ensure_aware(attempted_at) <= now - timedelta(seconds=retry_after_seconds)


def _artifact_output_language(artifact: TerminalArtifact) -> str | None:
    metadata = artifact.metadata_json if isinstance(artifact.metadata_json, dict) else {}
    value = metadata.get("output_language")
    return value if isinstance(value, str) and value.strip() else None


def _datetime_metadata_value(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
