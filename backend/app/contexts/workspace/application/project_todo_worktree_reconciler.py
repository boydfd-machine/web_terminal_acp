from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.git_worktree_coordinator import (
    process_git_worktree_snapshot_refresh,
)
from app.contexts.terminal_runtime.application.git_worktree_queries import (
    list_unresolved_git_worktree_window_targets,
)
from app.contexts.workspace.infrastructure.project_todo_worktrees_repository import (
    list_project_todo_worktree_attention_targets,
    sync_project_todo_worktree_summaries_for_window,
)
from app.models import Client, ClientRuntime
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
WORKTREE_RECONCILE_INTERVAL_SECONDS = 15.0
WORKTREE_RECONCILE_BATCH_SIZE = 50


async def process_project_todo_worktree_reconciliation_once(
    session_factory: SessionFactory,
    *,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub | None,
    limit: int = WORKTREE_RECONCILE_BATCH_SIZE,
) -> int:
    async with session_factory() as session:
        targets = await _collect_reconciliation_targets(session, limit=limit)
        if not targets:
            return 0

        runtimes = await _client_runtimes(session, {client_id for client_id, _window_id in targets})
        processed = 0
        changed_targets: list[tuple[UUID, UUID, bool]] = []
        for client_id, window_id in targets:
            snapshot_changed = await process_git_worktree_snapshot_refresh(
                session,
                client_id=client_id,
                window_id=window_id,
                registry=registry,
                client_runtime=runtimes.get(client_id),
                include_unresolved_runs=True,
            )
            todo_changed = await sync_project_todo_worktree_summaries_for_window(
                session,
                client_id,
                window_id,
            )
            if snapshot_changed or todo_changed:
                changed_targets.append((client_id, window_id, todo_changed))
            processed += 1

        if changed_targets:
            await session.commit()
        else:
            await session.rollback()

    if ui_event_hub is not None:
        for client_id, window_id, todo_changed in changed_targets:
            resources = ["window", "tree", "git_runs"]
            if todo_changed:
                resources.append("project_todos")
            with contextlib.suppress(Exception):
                await ui_event_hub.publish_invalidation(
                    resources,
                    client_id=client_id,
                    window_id=window_id,
                    reason="git_worktree_reconciled",
                )
    return processed


async def run_project_todo_worktree_reconciliation_loop(
    session_factory: SessionFactory,
    *,
    registry: ClientConnectionRegistry | None,
    ui_event_hub: UiEventHub | None,
    interval_seconds: float = WORKTREE_RECONCILE_INTERVAL_SECONDS,
) -> None:
    while True:
        try:
            await process_project_todo_worktree_reconciliation_once(
                session_factory,
                registry=registry,
                ui_event_hub=ui_event_hub,
            )
        except Exception:
            logger.exception("failed to reconcile git worktree merge status")
        await asyncio.sleep(interval_seconds)


async def _collect_reconciliation_targets(
    session: AsyncSession,
    *,
    limit: int,
) -> list[tuple[UUID, UUID]]:
    targets: list[tuple[UUID, UUID]] = []
    seen: set[tuple[UUID, UUID]] = set()
    for target in await list_project_todo_worktree_attention_targets(session, limit=limit):
        seen.add(target)
        targets.append(target)
    remaining = max(limit - len(targets), 0)
    if remaining == 0:
        return targets
    for target in await list_unresolved_git_worktree_window_targets(session, limit=remaining):
        if target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


async def _client_runtimes(
    session: AsyncSession,
    client_ids: set[UUID],
) -> dict[UUID, ClientRuntime]:
    if not client_ids:
        return {}
    rows = await session.execute(
        select(Client.id, Client.runtime).where(Client.id.in_(client_ids))
    )
    return {client_id: runtime for client_id, runtime in rows}
