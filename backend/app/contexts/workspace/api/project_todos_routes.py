from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.workspace.api import project_todo_comment_routes
from app.contexts.workspace.api.schemas import (
    ProjectTodoCreateIn,
    ProjectTodoDispatchIn,
    ProjectTodoListOut,
    ProjectTodoMoveProjectIn,
    ProjectTodoOut,
    ProjectTodoPatchIn,
    ProjectTodoReviewDispatchIn,
    ProjectTodoSearchOut,
)
from app.contexts.workspace.api.project_todo_responses import (
    project_todo_list_responses,
    project_todo_response,
)
from app.contexts.workspace.api.project_todo_invalidation import publish_project_todo_invalidation
from app.contexts.workspace.api.project_todo_route_helpers import (
    normalize_project_path,
    normalized_project_todo_search_query,
    project_todo_history_actor_from_request,
    require_client,
    require_todo,
)
from app.contexts.workspace.api.project_todo_runtime import artifact_runtime_deps, background_session_factory_for
from app.contexts.workspace.api.project_todo_schedule import (
    project_todo_schedule_from_create,
    project_todo_schedule_from_patch,
    project_todo_schedule_was_patched,
)
from app.contexts.workspace.application.project_todo_artifacts import (
    create_missing_project_todo_requested_artifacts,
    normalize_project_todo_artifact_kinds,
    pop_project_todo_artifact_generations,
    schedule_project_todo_requested_artifacts,
)
from app.contexts.workspace.application.project_todo_dispatch_prompt import (
    build_dispatch_prompt_for_project_todo,
)
from app.contexts.workspace.application.project_todo_completion_verification import make_verification_scheduler
from app.contexts.workspace.application.project_todo_input_artifacts import normalize_project_todo_input_artifact_ids
from app.contexts.workspace.application.project_todo_dispatch_queue import (
    prepare_project_todo_queued_dispatch,
)
from app.contexts.workspace.application.project_todo_dispatch_after import (
    dispatch_ready_project_todos,
    dispatch_ready_project_todos_after_dependency_satisfied,
    start_project_todo_window_dispatch,
)
from app.contexts.workspace.application.project_todo_date_filter import (
    ProjectTodoDateFilterError,
    project_todo_updated_bounds,
)
from app.contexts.workspace.application.project_todo_review_dispatch import (
    dispatch_project_todo_review_window,
)
from app.contexts.workspace.application.project_todo_dependencies import (
    ProjectTodoDependencyError,
    clear_project_todo_queued_dispatch,
    has_incomplete_dependencies,
    queue_project_todo_dispatch,
    set_project_todo_dependencies,
)
from app.contexts.workspace.application.project_todo_runs import apply_project_todo_schedule_patch
from app.contexts.workspace.application import project_todo_history as todo_history
from app.contexts.workspace.application.project_todo_types import get_project_todo_type
from app.contexts.workspace.application.project_todo_repository import (
    apply_project_todo_review_status,
    apply_project_todo_status,
    create_project_todo,
    list_project_todo_artifact_candidates,
    list_project_todos,
    move_project_todo_to_project,
    next_project_todo_sort_order,
    project_todo_can_move_project,
    resolve_project_todo_parent,
)
from app.contexts.workspace.application.project_queries import list_terminal_projects
from app.contexts.workspace.application.project_todo_search import search_project_todos
from app.models import ProjectTodoStatus
from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todos"])
router.include_router(project_todo_comment_routes.router)

ProjectTodoSearchLimit = Annotated[int, Query(ge=1, le=50)]
ProjectTodoSearchOffset = Annotated[int, Query(ge=0)]
ProjectTodoSearchQuery = Annotated[str, Query(min_length=1, max_length=512)]
ProjectTodoDateRangeQuery = Query(default=None, alias="range")

@router.get("", response_model=ProjectTodoListOut)
async def list_todos(
    client_id: UUID,
    project_path: str,
    request: Request,
    updated_range: str | None = ProjectTodoDateRangeQuery,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoListOut:
    await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    try:
        updated_bounds = project_todo_updated_bounds(
            updated_range,
            start_date=start_date,
            end_date=end_date,
        )
    except ProjectTodoDateFilterError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    registry = client_connection_registry_from_state(request.app.state)

    def remote_client_available(remote_client_id: UUID) -> bool:
        connection = registry.get(remote_client_id)
        return connection is not None and not getattr(connection, "closed", False)

    await dispatch_ready_project_todos(
        session=session,
        client_id=client_id,
        project_path=normalized_path,
        tmux_manager=tmux_manager,
        registry=registry,
        session_factory=background_session_factory_for(session),
        ui_event_hub=ui_event_hub_from_state(request.app.state),
    )
    todos = await list_project_todos(
        session,
        client_id,
        normalized_path,
        updated_at_start=updated_bounds.start,
        updated_at_end=updated_bounds.end,
        remote_client_available=remote_client_available,
        verification_scheduler=make_verification_scheduler(
            client_id=client_id,
            session_factory=background_session_factory_for(session),
            registry=registry,
        ),
    )
    artifact_source_todos = await list_project_todo_artifact_candidates(session, client_id, normalized_path)
    generations = await create_missing_project_todo_requested_artifacts(
        session,
        artifact_source_todos,
        remote_client_available=remote_client_available,
    )
    queued_generations = pop_project_todo_artifact_generations(session)
    if queued_generations:
        generations = [*queued_generations, *generations]
    if generations:
        await session.commit()
        schedule_project_todo_requested_artifacts(
            generations,
            artifact_runtime_deps(request, tmux_manager, session),
        )
    response_todos = await project_todo_list_responses(session, client_id, todos)
    await session.commit()
    return ProjectTodoListOut(todos=response_todos)

@router.get("/search", response_model=ProjectTodoSearchOut)
async def search_todos(
    client_id: UUID,
    q: ProjectTodoSearchQuery,
    project_path: str | None = None,
    limit: ProjectTodoSearchLimit = 25,
    offset: ProjectTodoSearchOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoSearchOut:
    await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path) if project_path is not None else None
    return await search_project_todos(
        session,
        client_id=client_id,
        query=normalized_project_todo_search_query(q),
        project_path=normalized_path,
        limit=limit,
        offset=offset,
    )

@router.get("/{todo_id}", response_model=ProjectTodoOut)
async def get_todo_detail(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    todo = await require_todo(session, client_id, normalize_project_path(project_path), todo_id)
    return await project_todo_response(session, client_id, todo)

@router.post("", response_model=ProjectTodoOut)
async def create_todo(
    client_id: UUID,
    project_path: str,
    payload: ProjectTodoCreateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    history_actor=Depends(project_todo_history_actor_from_request),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    try:
        artifact_kinds = (
            normalize_project_todo_artifact_kinds(payload.artifact_kinds)
            if "artifact_kinds" in payload.model_fields_set
            else None
        )
        input_artifact_ids = (
            normalize_project_todo_input_artifact_ids(payload.input_artifact_ids)
            if "input_artifact_ids" in payload.model_fields_set
            else None
        )
        todo = await create_project_todo(
            session,
            client_id,
            normalized_path,
            title=payload.title,
            description=payload.description,
            parent_todo_id=payload.parent_todo_id,
            todo_type_id=payload.todo_type_id,
            status=ProjectTodoStatus(payload.status),
            review_strategy=payload.review_strategy,
            review_agent=payload.review_agent,
            review_agent_profile_id=payload.review_agent_profile_id,
            schedule=project_todo_schedule_from_create(payload),
            artifact_kinds=artifact_kinds,
            input_artifact_ids=input_artifact_ids,
            artifact_model_selection=(
                payload.artifact_model_selection.model_dump(mode="json", exclude_none=True)
                if payload.artifact_model_selection is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await todo_history.record_created(session, todo, history_actor)
    await session.commit()
    await session.refresh(todo)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_created")
    return await project_todo_response(session, client_id, todo)

@router.patch("/{todo_id}", response_model=ProjectTodoOut)
async def patch_todo(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoPatchIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
    history_actor=Depends(project_todo_history_actor_from_request),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    todo = await require_todo(session, client_id, normalize_project_path(project_path), todo_id)
    history_before = todo_history.snapshot(todo)
    provided_fields = payload.model_fields_set
    if payload.title is not None:
        todo.title = payload.title
    if "description" in provided_fields:
        todo.description = payload.description
    if "parent_todo_id" in provided_fields:
        if todo.status != ProjectTodoStatus.todo:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="parent selection is locked")
        try:
            todo.parent_todo_id = await resolve_project_todo_parent(
                session,
                client_id,
                todo.project_path,
                todo.id,
                payload.parent_todo_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if "todo_type_id" in provided_fields:
        todo_type = await get_project_todo_type(session, client_id, todo.project_path, payload.todo_type_id or "default")
        if todo_type is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="todo type not found")
        todo.todo_type_id = todo_type.id
        if todo.assigned_window_id is None:
            todo.assigned_agent = todo_type.agent
            todo.agent_profile_id = todo_type.agent_profile_id
            todo.artifact_kinds_json = todo_type.artifact_kinds_json
            todo.input_artifact_ids_json = todo_type.input_artifact_ids_json
    status_before = todo.status
    status_after: ProjectTodoStatus | None = None
    if payload.sort_order is not None:
        todo.sort_order = payload.sort_order
    elif payload.status is not None and ProjectTodoStatus(payload.status) != status_before:
        todo.sort_order = await next_project_todo_sort_order(session, client_id, todo.project_path)
    if payload.status is not None:
        status_after = ProjectTodoStatus(payload.status)
        apply_project_todo_status(todo, status_after)
        # Pending is a queued TODO, so a same-status manual move to Todo must cancel it.
        await clear_project_todo_queued_dispatch(session, todo.id)
    if payload.review_strategy is not None:
        todo.review_strategy = payload.review_strategy
    if "review_agent" in provided_fields:
        todo.review_agent = payload.review_agent
    if "review_agent_profile_id" in provided_fields:
        todo.review_agent_profile_id = payload.review_agent_profile_id
    if "artifact_kinds" in provided_fields:
        if status_before != ProjectTodoStatus.todo:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="artifact selection is locked")
        try:
            artifact_kinds = normalize_project_todo_artifact_kinds(payload.artifact_kinds)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        todo.artifact_kinds_json = artifact_kinds or None
    if "input_artifact_ids" in provided_fields:
        if status_before != ProjectTodoStatus.todo:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="input artifact selection is locked")
        try:
            input_artifact_ids = normalize_project_todo_input_artifact_ids(payload.input_artifact_ids)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        todo.input_artifact_ids_json = input_artifact_ids or None
    if payload.review_status is not None:
        await apply_project_todo_review_status(session, todo, payload.review_status)
    if payload.needs_human_review is not None:
        todo.needs_human_review = payload.needs_human_review
        if payload.needs_human_review:
            await apply_project_todo_review_status(session, todo, "NEEDS_HUMAN_REVIEW")
    if payload.review_unseen is not None:
        todo.review_unseen = payload.review_unseen and todo.status == ProjectTodoStatus.awaiting_review
    if "review_notes" in provided_fields:
        todo.review_notes = payload.review_notes
    if project_todo_schedule_was_patched(provided_fields):
        try:
            apply_project_todo_schedule_patch(todo, project_todo_schedule_from_patch(todo, payload, provided_fields))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    assigned_window_id = todo.assigned_window_id
    await todo_history.record_update(session, todo, history_before, history_actor, provided_fields)
    await session.commit()
    await session.refresh(todo)
    dependency_satisfied_statuses = {ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done}
    if status_after in dependency_satisfied_statuses and status_before not in dependency_satisfied_statuses:
        await dispatch_ready_project_todos_after_dependency_satisfied(
            session=session,
            upstream_todo=todo,
            tmux_manager=tmux_manager,
            registry=client_connection_registry_from_state(request.app.state),
            session_factory=background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
        )
        await session.refresh(todo)
    await publish_project_todo_invalidation(
        request,
        client_id,
        window_id=assigned_window_id,
        reason="project_todo_updated",
    )
    return await project_todo_response(session, client_id, todo)

@router.post("/{todo_id}/move-project", response_model=ProjectTodoOut)
async def move_todo_project(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoMoveProjectIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    source_project_path = normalize_project_path(project_path)
    target_project_path = normalize_project_path(payload.project_path)
    todo = await require_todo(session, client_id, source_project_path, todo_id)
    if not await project_todo_can_move_project(session, todo):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only TODO cards can move projects")
    if target_project_path != source_project_path:
        projects = await list_terminal_projects(session, client_id, visible_since=None)
        if not any(project.project_path == target_project_path for project in projects):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target project not found")
        await move_project_todo_to_project(session, todo, target_project_path)
    await session.commit()
    await session.refresh(todo)
    await publish_project_todo_invalidation(request, client_id, reason="project_todo_moved_project")
    return await project_todo_response(session, client_id, todo)

@router.post("/{todo_id}/dispatch", response_model=ProjectTodoOut)
async def dispatch_todo(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoDispatchIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    todo = await require_todo(session, client_id, normalized_path, todo_id)
    if todo.status == ProjectTodoStatus.blocked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="todo is blocked")
    output_language = payload.output_language or get_settings().summary_output_language
    try:
        prompt = await build_dispatch_prompt_for_project_todo(
            session,
            client_id=client_id,
            project_path=normalized_path,
            todo=todo,
            payload_prompt=payload.prompt,
            output_language=output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        if payload.dispatch_after_todo_ids is not None:
            await set_project_todo_dependencies(session, todo, payload.dispatch_after_todo_ids)
    except ProjectTodoDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    artifact_model_selection = (
        payload.artifact_model_selection.model_dump(mode="json", exclude_none=True)
        if payload.artifact_model_selection is not None
        else None
    )
    if artifact_model_selection is not None:
        todo.artifact_model_selection_json = artifact_model_selection

    if await has_incomplete_dependencies(session, todo.id):
        todo.status = ProjectTodoStatus.todo
        if artifact_model_selection is not None:
            todo.artifact_model_selection_json = artifact_model_selection
        prepare_project_todo_queued_dispatch(
            todo,
            agent_launch=payload.agent_launch,
            prompt=prompt,
            output_language=output_language,
        )
        await queue_project_todo_dispatch(
            session,
            todo,
            agent_launch=payload.agent_launch,
            dispatch_mode=payload.dispatch_mode,
            prompt=prompt,
        )
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_invalidation(request, client_id, reason="project_todo_dispatch_queued")
        return await project_todo_response(session, client_id, todo)

    todo = await start_project_todo_window_dispatch(
        session=session,
        todo=todo,
        agent_launch=payload.agent_launch,
        dispatch_mode=payload.dispatch_mode,
        prompt=prompt,
        output_language=output_language,
        tmux_manager=tmux_manager,
        registry=client_connection_registry_from_state(request.app.state),
        session_factory=background_session_factory_for(session),
        ui_event_hub=ui_event_hub_from_state(request.app.state),
    )
    return await project_todo_response(session, client_id, todo)

@router.post("/{todo_id}/review/dispatch", response_model=ProjectTodoOut)
async def dispatch_todo_review(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    payload: ProjectTodoReviewDispatchIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> ProjectTodoOut:
    client = await require_client(session, client_id)
    normalized_path = normalize_project_path(project_path)
    todo = await require_todo(session, client_id, normalized_path, todo_id)
    if todo.status != ProjectTodoStatus.awaiting_review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="todo is not awaiting review")
    output_language = payload.output_language or todo.dispatch_output_language or get_settings().summary_output_language
    try:
        todo = await dispatch_project_todo_review_window(
            session=session,
            client=client,
            todo=todo,
            agent_launch=payload.agent_launch,
            tmux_manager=tmux_manager,
            registry=client_connection_registry_from_state(request.app.state),
            session_factory=background_session_factory_for(session),
            ui_event_hub=ui_event_hub_from_state(request.app.state),
            prompt=payload.prompt,
            output_language=output_language,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return await project_todo_response(session, client_id, todo)
