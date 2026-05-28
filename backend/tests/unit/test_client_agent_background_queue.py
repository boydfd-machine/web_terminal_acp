import asyncio
from uuid import UUID

import pytest

from app.routers.client_agent import (
    _TerminalOutputRecordingJob,
    _WindowFairMessageQueue,
    _enqueue_background_message,
    _terminal_output_recording_worker,
)
from app.services.runtime.protocol import AgentMessage


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")
OTHER_WINDOW_ID = UUID("11111111-2222-3333-4444-555555555555")


@pytest.mark.asyncio
async def test_terminal_output_enqueue_waits_when_queue_is_full_without_dropping() -> None:
    queue: asyncio.Queue[AgentMessage] = asyncio.Queue(maxsize=1)
    oldest = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    newest = AgentMessage(
        type="terminal_output",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        payload={"data": "newest"},
    )
    queue.put_nowait(oldest)

    enqueue_task = asyncio.create_task(
        _enqueue_background_message(
            queue,
            client_id=CLIENT_ID,
            message=newest,
            queue_name="terminal_output",
        )
    )
    await asyncio.sleep(0)

    assert not enqueue_task.done()
    assert queue.get_nowait() is oldest
    queue.task_done()
    await asyncio.wait_for(enqueue_task, timeout=0.1)
    assert queue.get_nowait() is newest
    queue.task_done()


@pytest.mark.asyncio
async def test_window_fair_message_queue_rotates_between_terminal_windows() -> None:
    queue = _WindowFairMessageQueue(maxsize=10)
    busy_1 = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    busy_2 = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    busy_3 = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    other = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=OTHER_WINDOW_ID)

    await queue.put(busy_1)
    await queue.put(busy_2)
    await queue.put(busy_3)
    await queue.put(other)

    assert await queue.get() is busy_1
    queue.task_done()
    assert await queue.get() is other
    queue.task_done()
    assert await queue.get() is busy_2
    queue.task_done()
    assert await queue.get() is busy_3
    queue.task_done()


@pytest.mark.asyncio
async def test_window_fair_message_queue_prioritizes_input_response_output() -> None:
    queue = _WindowFairMessageQueue(maxsize=10)
    busy_1 = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    busy_2 = AgentMessage(type="terminal_output", client_id=CLIENT_ID, window_id=WINDOW_ID)
    other_stale = AgentMessage(
        type="terminal_output",
        client_id=CLIENT_ID,
        window_id=OTHER_WINDOW_ID,
    )
    input_response = AgentMessage(
        type="terminal_output",
        client_id=CLIENT_ID,
        window_id=OTHER_WINDOW_ID,
        payload={"input_priority": True},
    )

    await queue.put(busy_1)
    await queue.put(busy_2)
    await queue.put(other_stale)
    await queue.put(input_response)

    assert await queue.get() is input_response
    queue.task_done()
    assert await queue.get() is busy_1
    queue.task_done()
    assert await queue.get() is other_stale
    queue.task_done()
    assert await queue.get() is busy_2
    queue.task_done()


@pytest.mark.asyncio
async def test_ai_event_enqueue_waits_when_queue_is_full_without_dropping() -> None:
    queue: asyncio.Queue[AgentMessage] = asyncio.Queue(maxsize=1)
    oldest = AgentMessage(type="ai_event", client_id=CLIENT_ID, window_id=WINDOW_ID)
    newest = AgentMessage(
        type="ai_event",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        payload={"payload": {"id": "newest"}},
    )
    queue.put_nowait(oldest)

    enqueue_task = asyncio.create_task(
        _enqueue_background_message(
            queue,
            client_id=CLIENT_ID,
            message=newest,
            queue_name="ai_event",
        )
    )
    await asyncio.sleep(0)

    assert not enqueue_task.done()
    assert queue.get_nowait() is oldest
    queue.task_done()
    await asyncio.wait_for(enqueue_task, timeout=0.1)
    assert queue.get_nowait() is newest
    queue.task_done()


@pytest.mark.asyncio
async def test_terminal_output_recording_worker_batches_plain_output_by_window(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.client_agent.TERMINAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS", 0.001)
    queue: asyncio.Queue[_TerminalOutputRecordingJob] = asyncio.Queue()
    handled: list[_TerminalOutputRecordingJob] = []

    async def handler(job: _TerminalOutputRecordingJob) -> None:
        handled.append(job)

    worker = asyncio.create_task(
        _terminal_output_recording_worker(client_id=CLIENT_ID, queue=queue, handler=handler)
    )
    try:
        await queue.put(_terminal_output_job(b"first"))
        await queue.put(_terminal_output_job(b"second"))
        await asyncio.wait_for(queue.join(), timeout=0.2)
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    assert [(job.window_id, job.clean_data) for job in handled] == [(WINDOW_ID, b"firstsecond")]


@pytest.mark.asyncio
async def test_terminal_output_recording_worker_flushes_before_marker_job(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.client_agent.TERMINAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS", 1.0)
    queue: asyncio.Queue[_TerminalOutputRecordingJob] = asyncio.Queue()
    handled: list[_TerminalOutputRecordingJob] = []

    async def handler(job: _TerminalOutputRecordingJob) -> None:
        handled.append(job)

    marker = {"command": "echo marker", "window_id": str(WINDOW_ID)}
    worker = asyncio.create_task(
        _terminal_output_recording_worker(client_id=CLIENT_ID, queue=queue, handler=handler)
    )
    try:
        await queue.put(_terminal_output_job(b"plain"))
        await queue.put(_terminal_output_job(b"", commands=(marker,)))
        await asyncio.wait_for(queue.join(), timeout=0.2)
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    assert len(handled) == 2
    assert handled[0].clean_data == b"plain"
    assert handled[0].commands == ()
    assert handled[1].clean_data == b""
    assert handled[1].commands == (marker,)


@pytest.mark.asyncio
async def test_terminal_output_recording_worker_does_not_join_before_batch_flush(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.client_agent.TERMINAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS", 0.05)
    queue: asyncio.Queue[_TerminalOutputRecordingJob] = asyncio.Queue()
    handled: list[_TerminalOutputRecordingJob] = []
    release_handler = asyncio.Event()

    async def handler(job: _TerminalOutputRecordingJob) -> None:
        handled.append(job)
        await release_handler.wait()

    worker = asyncio.create_task(
        _terminal_output_recording_worker(client_id=CLIENT_ID, queue=queue, handler=handler)
    )
    join_task: asyncio.Task[None] | None = None
    try:
        await queue.put(_terminal_output_job(b"pending"))
        join_task = asyncio.create_task(queue.join())
        await asyncio.sleep(0.01)

        assert not join_task.done()

        await asyncio.wait_for(_handled_count(handled, 1), timeout=0.2)
        assert not join_task.done()

        release_handler.set()
        await asyncio.wait_for(join_task, timeout=0.2)
    finally:
        if join_task is not None and not join_task.done():
            join_task.cancel()
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    assert handled[0].clean_data == b"pending"


def _terminal_output_job(
    clean_data: bytes,
    *,
    window_id: UUID = WINDOW_ID,
    commands: tuple[dict, ...] = (),
) -> _TerminalOutputRecordingJob:
    return _TerminalOutputRecordingJob(
        client_id=CLIENT_ID,
        window_id=window_id,
        clean_data=clean_data,
        commands=commands,
        worktree_markers=(),
    )


async def _handled_count(handled: list[_TerminalOutputRecordingJob], count: int) -> None:
    while len(handled) < count:
        await asyncio.sleep(0)
