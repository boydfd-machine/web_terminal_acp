from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_todo_responses import project_todo_response
from app.contexts.workspace.api.schemas import (
    ProjectTodoFromArtifactCardIn,
    ProjectTodoFromPageReviewCardIn,
    ProjectTodoOut,
)
from app.contexts.workspace.api.project_todo_schedule import project_todo_schedule_from_create
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_runtime import artifact_runtime_deps
from app.contexts.workspace.application.project_todo_artifacts import (
    normalize_project_todo_artifact_kinds,
    retry_failed_project_todo_artifact,
    schedule_project_todo_requested_artifacts,
)
from app.contexts.workspace.application.project_todo_input_artifacts import normalize_project_todo_input_artifact_ids
from app.contexts.workspace.application.project_todo_types import (
    DEFAULT_PROJECT_TODO_TYPE_ID,
    get_project_todo_type,
)
from app.contexts.workspace.application.project_todo_repository import (
    create_project_todo,
    get_project_todo,
    link_project_todo_artifact,
    source_project_todo_id_for_artifact,
)
from app.db import get_session
from app.models import ProjectTodoStatus, TerminalArtifact, TerminalArtifactStatus
from app.platform.plugins.artifact_plugins.page_review_cards import page_review_card_todo_payload
from app.platform.plugins.artifact_plugins.requirement_review_report import (
    requirement_review_card_todo_description,
)
from app.platform.plugins.artifact_plugins.project_todo_card_metadata import (
    normalize_project_todo_card_type_id,
    project_todo_card_artifact_kind_candidate,
)
from app.platform.ui_events import ui_event_hub_from_state
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])

_GENERATED_TODO_TYPE_ALIAS_CANDIDATES = {
    "bug": ("debug",),
    "fix": ("quick-fix",),
    "large": ("large-feature",),
    "performance": ("performance-optimization",),
    "product": ("product-design",),
    "research": ("solution-research",),
    "small": ("small-feature",),
    "ui": ("ui-change",),
    "ux": ("ui-change",),
}


@router.post("/from-artifact-card", response_model=ProjectTodoOut)
async def create_todo_from_artifact_card(
    client_id: UUID,
    project_path: str,
    payload: ProjectTodoFromArtifactCardIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    if await get_client(session, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    normalized_path = _normalize_project_path(project_path)
    artifact = await _require_ready_artifact(session, client_id, payload.artifact_id)
    source_todo_id = await source_project_todo_id_for_artifact(
        session,
        client_id,
        normalized_path,
        payload.artifact_id,
    )
    card = payload.card
    todo_type_id = await _safe_artifact_card_todo_type_id(
        session,
        client_id,
        normalized_path,
        card.todo_type_id,
    )
    try:
        artifact_kinds = (
            _safe_artifact_card_artifact_kinds(card.artifact_kinds)
            if "artifact_kinds" in card.model_fields_set
            else None
        )
        input_artifact_ids = (
            normalize_project_todo_input_artifact_ids(card.input_artifact_ids)
            if "input_artifact_ids" in card.model_fields_set
            else None
        )
        todo = await create_project_todo(
            session,
            client_id,
            normalized_path,
            title=card.title,
            description=_artifact_card_todo_description(artifact, card.description),
            # Artifact-created cards inherit ownership from the source todo link, not from iframe payload.
            parent_todo_id=source_todo_id,
            todo_type_id=todo_type_id,
            status=ProjectTodoStatus(card.status),
            review_strategy=card.review_strategy,
            review_agent=card.review_agent,
            review_agent_profile_id=card.review_agent_profile_id,
            schedule=project_todo_schedule_from_create(card),
            artifact_kinds=artifact_kinds,
            input_artifact_ids=input_artifact_ids,
            artifact_model_selection=(
                card.artifact_model_selection.model_dump(mode="json", exclude_none=True)
                if "artifact_model_selection" in card.model_fields_set
                and card.artifact_model_selection is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    link = await link_project_todo_artifact(session, todo, payload.artifact_id, purpose=payload.purpose)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    await session.commit()
    await session.refresh(todo)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["project_todos"],
        client_id=client_id,
        reason="project_todo_created_from_artifact_card",
    )
    return await project_todo_response(session, client_id, todo)


@router.post("/from-page-review-card", response_model=ProjectTodoOut)
async def create_todo_from_page_review_card(
    client_id: UUID,
    project_path: str,
    payload: ProjectTodoFromPageReviewCardIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    if await get_client(session, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    normalized_path = _normalize_project_path(project_path)
    artifact = await _require_page_review_artifact(session, client_id, payload.artifact_id)
    try:
        title, description = page_review_card_todo_payload(artifact.content_json or {}, payload.card_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page review card not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    todo = await create_project_todo(
        session,
        client_id,
        normalized_path,
        title=title,
        description=description,
        status=ProjectTodoStatus.todo,
    )
    link = await link_project_todo_artifact(session, todo, payload.artifact_id, purpose=payload.purpose)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    await session.commit()
    await session.refresh(todo)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["project_todos"],
        client_id=client_id,
        reason="project_todo_created_from_page_review_card",
    )
    return await project_todo_response(session, client_id, todo)


@router.post("/{todo_id}/artifacts/{link_id}/retry", response_model=ProjectTodoOut)
async def retry_todo_artifact(
    client_id: UUID,
    todo_id: UUID,
    link_id: UUID,
    project_path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    if await get_client(session, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    normalized_path = _normalize_project_path(project_path)
    todo = await get_project_todo(session, client_id, normalized_path, todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    try:
        generation = await retry_failed_project_todo_artifact(session, todo, link_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    schedule_project_todo_requested_artifacts(
        [generation],
        artifact_runtime_deps(request, tmux_manager, session),
    )
    await session.refresh(todo)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_artifact_retried")
    return await project_todo_response(session, client_id, todo)


async def _require_page_review_artifact(
    session: AsyncSession,
    client_id: UUID,
    artifact_id: UUID,
) -> TerminalArtifact:
    artifact = await _require_ready_artifact(session, client_id, artifact_id)
    if artifact.artifact_kind != "page_review_cards":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="artifact is not page_review_cards")
    return artifact


async def _require_ready_artifact(
    session: AsyncSession,
    client_id: UUID,
    artifact_id: UUID,
) -> TerminalArtifact:
    artifact = await session.scalar(
        select(TerminalArtifact).where(
            TerminalArtifact.id == artifact_id,
            TerminalArtifact.client_id == client_id,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    if artifact.status != TerminalArtifactStatus.succeeded:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="artifact is not ready")
    return artifact


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _safe_artifact_card_todo_type_id(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_type_id: str,
) -> str:
    for candidate in _artifact_card_todo_type_id_candidates(todo_type_id):
        todo_type = await get_project_todo_type(session, client_id, project_path, candidate)
        if todo_type is not None:
            return todo_type.id
    return DEFAULT_PROJECT_TODO_TYPE_ID


def _artifact_card_todo_type_id_candidates(todo_type_id: str) -> tuple[str, ...]:
    candidates: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    raw = todo_type_id.strip().lower()
    add(todo_type_id)
    add(raw)
    for alias in _GENERATED_TODO_TYPE_ALIAS_CANDIDATES.get(raw, ()):
        add(alias)
    normalized_id = normalize_project_todo_card_type_id(todo_type_id)
    if normalized_id != DEFAULT_PROJECT_TODO_TYPE_ID:
        add(normalized_id)
    return tuple(candidates)


def _safe_artifact_card_artifact_kinds(artifact_kinds: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_kind in artifact_kinds or []:
        canonical = _artifact_card_artifact_kind(raw_kind)
        if canonical is None or canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        normalized.append(canonical)
    return normalized


def _artifact_card_todo_description(artifact: TerminalArtifact, description: str | None) -> str | None:
    if artifact.artifact_kind == "requirement_review_report":
        return requirement_review_card_todo_description(description)
    return description


def _artifact_card_artifact_kind(raw_kind: str) -> str | None:
    candidate = project_todo_card_artifact_kind_candidate(raw_kind)
    if candidate is None:
        return None
    try:
        return normalize_project_todo_artifact_kinds([candidate])[0]
    except (IndexError, ValueError):
        return None
