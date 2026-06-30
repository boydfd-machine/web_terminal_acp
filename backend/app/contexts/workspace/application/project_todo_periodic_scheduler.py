from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import logging

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.workspace.application.project_todo_dispatch import (
    build_project_todo_prompt,
)
from app.contexts.workspace.application.project_todo_dispatch_after import (
    start_project_todo_window_dispatch,
)
from app.contexts.workspace.application.project_todo_repository import referenced_project_todos_for_todos
from app.contexts.workspace.application.project_todo_reference_context import (
    prompt_references_for_project_todos,
)
from app.contexts.workspace.infrastructure.project_todo_runs_repository import (
    due_cron_project_todos,
    schedule_next_project_todo_cron,
)
from app.platform.common_schemas import AgentLaunchIn
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
PERIODIC_TODO_INTERVAL_SECONDS = 30.0
PERIODIC_TODO_BATCH_SIZE = 10


async def process_project_todo_cron_triggers_once(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub,
    limit: int = PERIODIC_TODO_BATCH_SIZE,
) -> int:
    async with session_factory() as session:
        due_todos = await due_cron_project_todos(session, limit=limit)
        processed = 0
        for todo in due_todos:
            launch = _agent_launch_from_todo(todo.last_agent_launch_json)
            if launch is None:
                await schedule_next_project_todo_cron(session, todo)
                await session.commit()
                await ui_event_hub.publish_invalidation(
                    ["project_todos"],
                    client_id=todo.client_id,
                    reason="project_todo_cron_skipped",
                )
                continue
            referenced = (await referenced_project_todos_for_todos(session, [todo])).get(todo.id, [])
            prompt = build_project_todo_prompt(
                project_path=todo.project_path,
                title=todo.title,
                description=todo.description,
                output_language=todo.dispatch_output_language,
                referenced_todos=await prompt_references_for_project_todos(session, referenced),
            )
            await start_project_todo_window_dispatch(
                session=session,
                todo=todo,
                agent_launch=launch,
                dispatch_mode=todo.last_dispatch_mode or "submit",
                prompt=prompt,
                output_language=todo.dispatch_output_language,
                tmux_manager=tmux_manager,
                registry=registry,
                session_factory=session_factory,
                ui_event_hub=ui_event_hub,
                trigger_reason="cron",
            )
            processed += 1
        return processed


async def run_project_todo_periodic_scheduler_loop(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub,
    interval_seconds: float = PERIODIC_TODO_INTERVAL_SECONDS,
) -> None:
    while True:
        try:
            await process_project_todo_cron_triggers_once(
                session_factory,
                tmux_manager=tmux_manager,
                registry=registry,
                ui_event_hub=ui_event_hub,
            )
        except Exception:
            logger.exception("failed to process periodic project todos")
        await asyncio.sleep(interval_seconds)


def _agent_launch_from_todo(value: object) -> AgentLaunchIn | None:
    if not isinstance(value, dict):
        return None
    try:
        return AgentLaunchIn.model_validate(value)
    except ValidationError:
        logger.warning("periodic project todo has invalid stored agent launch")
        return None
