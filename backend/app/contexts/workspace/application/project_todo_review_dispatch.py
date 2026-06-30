from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.runtime_client import runtime_client_from_model
from app.contexts.windows.application.window_creation import create_virtual_window_for_client
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.workspace.application.project_todo_dispatch import (
    build_project_todo_review_prompt,
    schedule_project_todo_prompt_dispatch,
)
from app.contexts.workspace.application.project_todo_prompt_references import (
    project_todo_prompt_with_output_language,
)
from app.contexts.workspace.infrastructure.project_todo_reviews_repository import (
    create_local_review_target,
    create_project_todo_review_run,
    create_project_todo_work_snapshot,
    latest_project_todo_review_target,
)
from app.contexts.workspace.infrastructure.project_review_config_repository import (
    DEFAULT_REVIEW_AGENT_PROFILE_ID,
)
from app.models import Client, ProjectReviewConfig, ProjectTodo, ProjectTodoStatus
from app.platform.ui_events import UiEventHub
from app.platform.common_schemas import AgentLaunchIn

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
AUTO_REVIEW_INTERVAL_SECONDS = 5.0
AUTO_REVIEW_BATCH_SIZE = 5


async def dispatch_project_todo_review_window(
    *,
    session: AsyncSession,
    client: Client,
    todo: ProjectTodo,
    agent_launch: AgentLaunchIn,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    prompt: str | None = None,
    output_language: str | None = None,
) -> ProjectTodo:
    target = await latest_project_todo_review_target(session, todo.id)
    if target is None:
        snapshot = await create_project_todo_work_snapshot(
            session,
            todo,
            role="implementation",
            window_id=todo.assigned_window_id,
            worktree_summary=todo.implementation_worktree_json,
        )
        target = await create_local_review_target(session, todo, snapshot)
    effective_output_language = output_language or todo.dispatch_output_language
    if prompt is None:
        review_prompt = build_project_todo_review_prompt(
            project_path=todo.project_path,
            title=todo.title,
            description=todo.description,
            implementation_worktree=todo.implementation_worktree_json,
            output_language=effective_output_language,
        )
    else:
        review_prompt = project_todo_prompt_with_output_language(prompt, effective_output_language)
    await session.commit()
    result = await create_virtual_window_for_client(
        runtime_client_from_model(client),
        WindowCreateIn(cwd=_review_cwd(todo), agent_launch=agent_launch),
        session,
        tmux_manager,
        registry,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )

    run = await create_project_todo_review_run(
        session,
        todo,
        target,
        agent_client=agent_launch.agent,
        agent_profile_id=agent_launch.profile_id,
    )
    todo.review_status = "RUNNING"
    todo.review_agent = agent_launch.agent
    todo.review_agent_profile_id = agent_launch.profile_id
    todo.review_window_id = result.window.id
    todo.review_prompt = review_prompt
    todo.dispatch_output_language = effective_output_language
    todo.review_dispatched_at = datetime.now(UTC)
    todo.reviewed_at = None
    run.status = "RUNNING"
    run.review_window_id = result.window.id
    run.started_at = todo.review_dispatched_at
    await session.commit()
    await session.refresh(todo)
    schedule_project_todo_prompt_dispatch(
        client_id=todo.client_id,
        window_id=result.window.id,
        prompt=review_prompt,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        registry=registry,
    )
    await ui_event_hub.publish_invalidation(
        ["tree", "window", "search", "project_todos"],
        client_id=todo.client_id,
        window_id=result.window.id,
        reason="project_todo_review_dispatched",
    )
    return todo


async def process_project_todo_auto_reviews_once(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub,
    limit: int = AUTO_REVIEW_BATCH_SIZE,
) -> int:
    async with session_factory() as session:
        rows = list(
            await session.execute(
                select(ProjectTodo, ProjectReviewConfig)
                .join(
                    ProjectReviewConfig,
                    (ProjectReviewConfig.client_id == ProjectTodo.client_id)
                    & (ProjectReviewConfig.project_path == ProjectTodo.project_path),
                )
                .where(
                    ProjectTodo.status == ProjectTodoStatus.awaiting_review,
                    ProjectTodo.review_status == "PENDING",
                    ProjectTodo.review_window_id.is_(None),
                    ProjectReviewConfig.pr_provider == "LOCAL_CARD",
                    ProjectReviewConfig.auto_dispatch_review.is_(True),
                    ProjectReviewConfig.review_agent.is_not(None),
                )
                .order_by(ProjectTodo.awaiting_review_at, ProjectTodo.id)
                .limit(limit)
            )
        )
        processed = 0
        for todo, config in rows:
            client = await get_client(session, todo.client_id)
            if client is None or config.review_agent is None:
                continue
            launch = AgentLaunchIn(
                agent=config.review_agent,
                command=config.review_agent_command or config.review_agent,
                profile_id=config.review_agent_profile_id or DEFAULT_REVIEW_AGENT_PROFILE_ID,
            )
            try:
                await dispatch_project_todo_review_window(
                    session=session,
                    client=client,
                    todo=todo,
                    agent_launch=launch,
                    tmux_manager=tmux_manager,
                    registry=registry,
                    session_factory=session_factory,
                    ui_event_hub=ui_event_hub,
                )
            except WindowServiceError as exc:
                await _mark_auto_review_failed(session_factory, todo.id, exc.detail)
                await ui_event_hub.publish_invalidation(
                    ["project_todos"],
                    client_id=todo.client_id,
                    reason="project_todo_auto_review_failed",
                )
            else:
                processed += 1
        return processed


async def run_project_todo_auto_review_loop(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub,
    interval_seconds: float = AUTO_REVIEW_INTERVAL_SECONDS,
) -> None:
    while True:
        try:
            await process_project_todo_auto_reviews_once(
                session_factory,
                tmux_manager=tmux_manager,
                registry=registry,
                ui_event_hub=ui_event_hub,
            )
        except Exception:
            logger.exception("failed to process project todo auto reviews")
        await asyncio.sleep(interval_seconds)


async def _mark_auto_review_failed(
    session_factory: SessionFactory,
    todo_id: UUID,
    detail: object,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        todo.review_status = "NEEDS_HUMAN_REVIEW"
        todo.needs_human_review = True
        todo.review_notes = f"Auto review dispatch failed: {detail}"
        todo.reviewed_at = datetime.now(UTC)
        await session.commit()


def _review_cwd(todo: ProjectTodo) -> str:
    worktree = todo.implementation_worktree_json
    if isinstance(worktree, dict):
        worktree_root = worktree.get("worktree_root")
        if isinstance(worktree_root, str) and worktree_root.strip():
            return worktree_root
    return todo.project_path
