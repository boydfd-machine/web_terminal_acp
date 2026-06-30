from __future__ import annotations

import asyncio
import contextlib
from uuid import uuid4

import pytest

from app.contexts.terminal_runtime.api.local_recording_routes import (
    LocalTerminalOutputRecordJob,
    LocalTerminalOutputRecorder,
    LocalTerminalOutputRecorderDependencies,
)


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self) -> None:
        return None


class FakeUiHub:
    async def publish_invalidation(self, *args, **kwargs) -> None:
        return None

    async def publish_debounced_invalidation(self, *args, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_local_git_worktree_tracking_jobs_are_serialized() -> None:
    client_id = uuid4()
    window_id = uuid4()
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first = asyncio.Event()
    call_count = 0

    async def record_command_markers(*args, **kwargs):
        return []

    async def record_output_chunk(*args, **kwargs):
        return False

    async def process_worktree_registration(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_started.set()
            await release_first.wait()
            return
        second_started.set()

    async def process_terminal_commands_for_git(*args, **kwargs):
        return None

    async def process_git_worktree_snapshot_refresh(*args, **kwargs):
        return False

    async def refresh_project_todo_worktree_summaries_for_window(*args, **kwargs):
        return False

    recorder = LocalTerminalOutputRecorder(
        LocalTerminalOutputRecorderDependencies(
            client_id=client_id,
            session_factory=FakeSession,
            ready_es_client=lambda: None,
            ui_event_hub=FakeUiHub,
            record_command_markers=record_command_markers,
            record_output_chunk=record_output_chunk,
            commands_need_git_worktree_tracking=lambda commands: False,
            git_worktree_agent_run_sequences=lambda commands: set(),
            process_git_worktree_snapshot_refresh=process_git_worktree_snapshot_refresh,
            process_terminal_commands_for_git=process_terminal_commands_for_git,
            process_worktree_registration=process_worktree_registration,
            refresh_project_todo_worktree_summaries_for_window=refresh_project_todo_worktree_summaries_for_window,
        ),
        batch_bytes=1024,
        batch_delay_seconds=0.001,
    )

    marker = {"window_id": str(window_id), "worktree_root": "/repo/.worktrees/test"}
    recorder.queue(LocalTerminalOutputRecordJob(window_id, b"", [], [marker], False))

    try:
        await asyncio.wait_for(first_started.wait(), timeout=0.2)
        recorder.queue(LocalTerminalOutputRecordJob(window_id, b"", [], [marker], False))
        await asyncio.wait_for(recorder._queue.join(), timeout=0.2)  # noqa: SLF001
        await asyncio.sleep(0.02)
        assert second_started.is_set() is False

        release_first.set()
        await asyncio.wait_for(second_started.wait(), timeout=0.2)
        await asyncio.wait_for(recorder._git_queue.join(), timeout=0.2)  # noqa: SLF001
    finally:
        release_first.set()
        for task in (recorder._worker_task, recorder._git_worker_task):  # noqa: SLF001
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
async def test_local_git_worktree_tracking_coalesces_queued_window_bursts() -> None:
    client_id = uuid4()
    window_id = uuid4()
    calls: list[list[dict]] = []
    snapshot_calls = 0

    async def record_command_markers(*args, **kwargs):
        return []

    async def record_output_chunk(*args, **kwargs):
        return False

    async def process_worktree_registration(*args, marker, **kwargs):
        calls.append([marker])

    async def process_terminal_commands_for_git(*args, **kwargs):
        return None

    async def process_git_worktree_snapshot_refresh(*args, **kwargs):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return False

    async def refresh_project_todo_worktree_summaries_for_window(*args, **kwargs):
        return False

    recorder = LocalTerminalOutputRecorder(
        LocalTerminalOutputRecorderDependencies(
            client_id=client_id,
            session_factory=FakeSession,
            ready_es_client=lambda: None,
            ui_event_hub=FakeUiHub,
            record_command_markers=record_command_markers,
            record_output_chunk=record_output_chunk,
            commands_need_git_worktree_tracking=lambda commands: False,
            git_worktree_agent_run_sequences=lambda commands: set(),
            process_git_worktree_snapshot_refresh=process_git_worktree_snapshot_refresh,
            process_terminal_commands_for_git=process_terminal_commands_for_git,
            process_worktree_registration=process_worktree_registration,
            refresh_project_todo_worktree_summaries_for_window=refresh_project_todo_worktree_summaries_for_window,
        ),
        batch_bytes=1024,
        batch_delay_seconds=0.001,
    )

    marker_a = {"window_id": str(window_id), "worktree_root": "/repo/.worktrees/a"}
    marker_b = {"window_id": str(window_id), "worktree_root": "/repo/.worktrees/b"}
    await recorder._git_queue.put(  # noqa: SLF001
        LocalTerminalOutputRecordJob(window_id, b"", [], [marker_a], False)
    )
    await recorder._git_queue.put(  # noqa: SLF001
        LocalTerminalOutputRecordJob(window_id, b"", [], [marker_b], False)
    )
    recorder._git_worker_task = asyncio.create_task(recorder._git_worker())  # noqa: SLF001

    await asyncio.wait_for(recorder._git_queue.join(), timeout=0.2)  # noqa: SLF001

    assert calls == [[marker_a], [marker_b]]
    assert snapshot_calls == 1
