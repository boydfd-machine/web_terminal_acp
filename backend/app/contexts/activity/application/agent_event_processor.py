from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.client_agent.ai_events import ManagedAiEvent
from app.contexts.activity.application.agent_activity_projection import event_is_agent_completion
from app.contexts.activity.application.agent_event_ingest import (
    index_managed_agent_event_if_ready,
    persist_managed_agent_event,
)
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.git_worktree_agent_markers import (
    extract_worktree_markers_from_agent_payload,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator import (
    process_git_worktree_snapshot_refresh,
    process_worktree_registration,
)
from app.contexts.workspace.application.project_todo_artifacts import (
    pop_project_todo_artifact_generations,
)
from app.contexts.workspace.application.project_todo_worktrees import (
    refresh_project_todo_worktree_summaries_for_window,
)
from app.models import Event, VirtualWindow
from app.platform.ui_events import UiEventHub


@dataclass(frozen=True)
class AgentEventProcessResult:
    row: Event
    resources: tuple[str, ...]
    git_worktree_changed: bool = False
    project_todo_artifact_generations: int = 0


async def process_managed_agent_event(
    session: AsyncSession,
    event: ManagedAiEvent,
    *,
    es_client: AsyncElasticsearch | None = None,
    ui_event_hub: UiEventHub | None = None,
    registry: ClientConnectionRegistry | None = None,
) -> AgentEventProcessResult:
    row = await persist_managed_agent_event(session, event, registry=registry)
    await session.commit()
    project_todo_artifact_generations = len(pop_project_todo_artifact_generations(session))

    if await index_managed_agent_event_if_ready(session, es_client, row):
        await session.commit()

    git_worktree_changed = await process_agent_event_git_worktree_tracking(
        session,
        event,
        registry=registry,
    )
    if git_worktree_changed:
        await session.commit()

    resources = ["agent_record", "window", "search"]
    if event_is_agent_completion(row):
        resources.append("project_todos")
    if git_worktree_changed:
        resources.extend(["tree", "git_runs"])
        if "project_todos" not in resources:
            resources.append("project_todos")

    if ui_event_hub is not None:
        await ui_event_hub.publish_invalidation(
            resources,
            client_id=event.client_id,
            window_id=event.window_id,
            reason="ai_event",
        )

    return AgentEventProcessResult(
        row=row,
        resources=tuple(resources),
        git_worktree_changed=git_worktree_changed,
        project_todo_artifact_generations=project_todo_artifact_generations,
    )


async def process_agent_event_git_worktree_tracking(
    session: AsyncSession,
    event: ManagedAiEvent,
    *,
    registry: ClientConnectionRegistry | None = None,
) -> bool:
    markers = extract_worktree_markers_from_agent_payload(event.payload)
    can_change_worktree = _agent_payload_can_change_worktree(event.payload)
    if not markers and not can_change_worktree:
        return False

    window = await session.scalar(
        select(VirtualWindow)
        .options(selectinload(VirtualWindow.client))
        .where(
            VirtualWindow.id == event.window_id,
            VirtualWindow.client_id == event.client_id,
        )
    )
    if window is None:
        return False

    changed = False
    for marker in markers:
        if str(marker.get("window_id")) != str(event.window_id):
            continue
        await process_worktree_registration(
            session,
            client_id=event.client_id,
            window_id=event.window_id,
            marker=marker,
            registry=registry,
            client_runtime=window.client.runtime if window.client is not None else None,
        )
        changed = True

    snapshot_changed = await process_git_worktree_snapshot_refresh(
        session,
        client_id=event.client_id,
        window_id=event.window_id,
        registry=registry,
        client_runtime=window.client.runtime if window.client is not None else None,
    )
    if snapshot_changed:
        await refresh_project_todo_worktree_summaries_for_window(
            session,
            client_id=event.client_id,
            window_id=event.window_id,
        )
    return changed or snapshot_changed


async def process_managed_agent_event_with_session_factory(
    session_factory: async_sessionmaker[AsyncSession],
    event: ManagedAiEvent,
    *,
    es_client: AsyncElasticsearch | None = None,
    ui_event_hub: UiEventHub | None = None,
    registry: ClientConnectionRegistry | None = None,
) -> AgentEventProcessResult:
    async with session_factory() as session:
        return await process_managed_agent_event(
            session,
            event,
            es_client=es_client,
            ui_event_hub=ui_event_hub,
            registry=registry,
        )


def _agent_payload_can_change_worktree(payload: Any) -> bool:
    stack: list[tuple[Any, int]] = [(payload, 0)]
    visited = 0
    while stack and visited < 128:
        value, depth = stack.pop()
        visited += 1
        if isinstance(value, dict):
            payload_type = value.get("type")
            if payload_type == "function_call_output":
                return True
            if depth < 6:
                stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list | tuple) and depth < 6:
            stack.extend((item, depth + 1) for item in value)
    return False
