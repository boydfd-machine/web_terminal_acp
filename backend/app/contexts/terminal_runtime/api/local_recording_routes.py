from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalTerminalOutputRecordJob:
    target_window_id: UUID
    clean_data: bytes
    commands: list
    worktree_markers: list
    is_attach_snapshot: bool


@dataclass(frozen=True)
class LocalTerminalOutputRecorderDependencies:
    client_id: UUID
    session_factory: Callable
    ready_es_client: Callable
    ui_event_hub: Callable
    record_command_markers: Callable
    record_output_chunk: Callable
    commands_need_git_worktree_tracking: Callable
    git_worktree_agent_run_sequences: Callable
    process_git_worktree_snapshot_refresh: Callable
    process_terminal_commands_for_git: Callable
    process_worktree_registration: Callable
    refresh_project_todo_worktree_summaries_for_window: Callable


class LocalTerminalOutputRecorder:
    def __init__(
        self,
        dependencies: LocalTerminalOutputRecorderDependencies,
        *,
        batch_bytes: int,
        batch_delay_seconds: float,
    ) -> None:
        self._dependencies = dependencies
        self._batch_bytes = batch_bytes
        self._batch_delay_seconds = batch_delay_seconds
        self._queue: asyncio.Queue[LocalTerminalOutputRecordJob] = asyncio.Queue()
        self._git_queue: asyncio.Queue[LocalTerminalOutputRecordJob] = asyncio.Queue()
        self._git_lookahead: list[tuple[LocalTerminalOutputRecordJob, int]] = []
        self._worker_task: asyncio.Task[None] | None = None
        self._git_worker_task: asyncio.Task[None] | None = None

    def queue(self, job: LocalTerminalOutputRecordJob) -> None:
        self._queue.put_nowait(job)
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _record_terminal_output(
        self,
        target_window_id: UUID,
        clean_data: bytes,
        commands: list,
        *,
        is_attach_snapshot: bool,
    ) -> None:
        if is_attach_snapshot or (not clean_data and not commands):
            return
        deps = self._dependencies
        try:
            async with deps.session_factory() as session:
                command_events = await deps.record_command_markers(
                    session,
                    deps.client_id,
                    target_window_id,
                    commands,
                )
                if command_events:
                    with contextlib.suppress(Exception):
                        await deps.ui_event_hub().publish_invalidation(
                            ["agent_record", "command_history", "window", "search"],
                            client_id=deps.client_id,
                            window_id=target_window_id,
                            reason="terminal_command",
                        )
                output_recorded = False
                if clean_data:
                    output_recorded = await deps.record_output_chunk(
                        session,
                        deps.client_id,
                        target_window_id,
                        clean_data,
                        deps.ready_es_client(),
                    )
                if output_recorded:
                    with contextlib.suppress(Exception):
                        await deps.ui_event_hub().publish_debounced_invalidation(
                            ("terminal_output", deps.client_id, target_window_id),
                            ["window", "search"],
                            client_id=deps.client_id,
                            window_id=target_window_id,
                            reason="terminal_output",
                            delay_seconds=1.0,
                        )
        except Exception:
            logger.exception("terminal output recording failed")

    async def _record_git_worktree_tracking(
        self,
        target_window_id: UUID,
        commands: list,
        worktree_markers: list,
        *,
        is_attach_snapshot: bool,
    ) -> None:
        deps = self._dependencies
        command_list = list(commands)
        commands_require_git = deps.commands_need_git_worktree_tracking(command_list)
        if is_attach_snapshot or (not worktree_markers and not commands_require_git):
            return
        try:
            changed = False
            todo_changed = False
            async with deps.session_factory() as session:
                for marker in worktree_markers:
                    if str(marker.get("window_id")) != str(target_window_id):
                        continue
                    await deps.process_worktree_registration(
                        session,
                        client_id=deps.client_id,
                        window_id=target_window_id,
                        marker=marker,
                        registry=None,
                    )
                    changed = True
                if commands_require_git:
                    await deps.process_terminal_commands_for_git(
                        session,
                        client_id=deps.client_id,
                        window_id=target_window_id,
                        commands=command_list,
                        registry=None,
                    )
                    changed = True
                if not changed:
                    return
                await session.commit()
                snapshot_changed = await deps.process_git_worktree_snapshot_refresh(
                    session,
                    client_id=deps.client_id,
                    window_id=target_window_id,
                    registry=None,
                    command_sequences=deps.git_worktree_agent_run_sequences(command_list) or None,
                )
                if snapshot_changed:
                    todo_changed = await deps.refresh_project_todo_worktree_summaries_for_window(
                        session,
                        client_id=deps.client_id,
                        window_id=target_window_id,
                    )
                    await session.commit()
            if changed or snapshot_changed:
                with contextlib.suppress(Exception):
                    resources = ["window", "tree", "git_runs"]
                    if todo_changed:
                        resources.append("project_todos")
                    await deps.ui_event_hub().publish_invalidation(
                        resources,
                        client_id=deps.client_id,
                        window_id=target_window_id,
                        reason="git_worktree",
                    )
        except Exception:
            logger.exception("local git worktree tracking failed")

    async def _record_terminal_output_task(
        self,
        target_window_id: UUID,
        clean_data: bytes,
        commands: list,
        worktree_markers: list,
        *,
        is_attach_snapshot: bool,
    ) -> None:
        await self._record_terminal_output(
            target_window_id,
            clean_data,
            commands,
            is_attach_snapshot=is_attach_snapshot,
        )
        if worktree_markers or self._dependencies.commands_need_git_worktree_tracking(list(commands)):
            self._git_queue.put_nowait(
                LocalTerminalOutputRecordJob(
                    target_window_id,
                    b"",
                    commands,
                    worktree_markers,
                    is_attach_snapshot,
                )
            )
            if self._git_worker_task is None or self._git_worker_task.done():
                self._git_worker_task = asyncio.create_task(self._git_worker())

    async def _git_worker(self) -> None:
        while True:
            try:
                job, done_count = await self._next_git_job()
            except asyncio.TimeoutError:
                if self._git_queue.empty():
                    return
                continue
            try:
                await self._record_git_worktree_tracking(
                    job.target_window_id,
                    job.commands,
                    job.worktree_markers,
                    is_attach_snapshot=job.is_attach_snapshot,
                )
            finally:
                for _ in range(done_count):
                    self._git_queue.task_done()

    async def _next_git_job(self) -> tuple[LocalTerminalOutputRecordJob, int]:
        if self._git_lookahead:
            job, done_count = self._git_lookahead.pop(0)
        else:
            job = await asyncio.wait_for(
                self._git_queue.get(),
                timeout=self._batch_delay_seconds,
            )
            done_count = 1
        commands = list(job.commands)
        markers = list(job.worktree_markers)
        is_attach_snapshot = job.is_attach_snapshot
        while True:
            try:
                next_job = self._git_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if next_job.target_window_id != job.target_window_id:
                self._git_lookahead.append((next_job, 1))
                break
            commands.extend(next_job.commands)
            markers.extend(next_job.worktree_markers)
            is_attach_snapshot = is_attach_snapshot and next_job.is_attach_snapshot
            done_count += 1
        return (
            LocalTerminalOutputRecordJob(
                job.target_window_id,
                b"",
                commands,
                markers,
                is_attach_snapshot,
            ),
            done_count,
        )

    @staticmethod
    def _can_batch(job: LocalTerminalOutputRecordJob) -> bool:
        return (
            bool(job.clean_data)
            and not job.commands
            and not job.worktree_markers
            and not job.is_attach_snapshot
        )

    async def _worker(self) -> None:
        pending_window_id: UUID | None = None
        pending_data = bytearray()

        async def flush_pending() -> None:
            nonlocal pending_window_id, pending_data
            if pending_window_id is None or not pending_data:
                return
            target_window_id = pending_window_id
            data = bytes(pending_data)
            pending_window_id = None
            pending_data = bytearray()
            await self._record_terminal_output_task(
                target_window_id,
                data,
                [],
                [],
                is_attach_snapshot=False,
            )

        while True:
            if pending_data and len(pending_data) >= self._batch_bytes:
                await flush_pending()
                continue

            try:
                if pending_data:
                    job = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._batch_delay_seconds,
                    )
                else:
                    job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            except asyncio.TimeoutError:
                await flush_pending()
                if self._queue.empty():
                    return
                continue

            try:
                if self._can_batch(job):
                    if (
                        pending_window_id is not None
                        and (
                            pending_window_id != job.target_window_id
                            or len(pending_data) + len(job.clean_data) > self._batch_bytes
                        )
                    ):
                        await flush_pending()
                    pending_window_id = job.target_window_id
                    pending_data.extend(job.clean_data)
                    continue

                await flush_pending()
                await self._record_terminal_output_task(
                    job.target_window_id,
                    job.clean_data,
                    job.commands,
                    job.worktree_markers,
                    is_attach_snapshot=job.is_attach_snapshot,
                )
            finally:
                self._queue.task_done()
