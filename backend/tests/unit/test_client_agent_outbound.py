import asyncio
from uuid import UUID

import pytest

from app.client_agent.outbound import (
    BulkUploadWriter,
    ControlMessageWriter,
    OutboundWriterClosed,
)
from app.services.runtime.protocol import AgentMessage, TerminalPayload, decode_agent_message


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")
OTHER_WINDOW_ID = UUID("11111111-2222-3333-4444-555555555555")


def _terminal_message(
    data: bytes,
    request_id: str,
    *,
    window_id: UUID = WINDOW_ID,
) -> AgentMessage:
    payload = TerminalPayload.from_bytes(window_id, data).model_dump(mode="json")
    return AgentMessage(
        type="terminal_output",
        client_id=CLIENT_ID,
        window_id=window_id,
        request_id=request_id,
        payload=payload,
    )


def _ai_event(request_id: str) -> AgentMessage:
    return AgentMessage(
        type="ai_event",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        request_id=request_id,
        payload={"payload": {"id": request_id}},
    )


def _status_event(request_id: str) -> AgentMessage:
    return AgentMessage(
        type="agent_work_presence",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        request_id=request_id,
        payload={"providers": ["codex"], "reasons": ["process"]},
    )


@pytest.mark.asyncio
async def test_control_message_writer_serializes_heartbeat_then_inventory_in_order() -> None:
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)

    writer = ControlMessageWriter(send)
    writer.start()
    try:
        heartbeat = AgentMessage(type="heartbeat", client_id=CLIENT_ID, request_id="heartbeat-1")
        inventory = AgentMessage(
            type="inventory",
            client_id=CLIENT_ID,
            request_id="inventory-1",
            payload={"windows": []},
        )

        await writer.send(heartbeat)
        await writer.send(inventory)
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [heartbeat, inventory]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_control_message_writer_prioritizes_terminal_control_over_git_worktree_results() -> None:
    sent: list[str] = []
    release_send = asyncio.Event()
    first_send_started = asyncio.Event()

    async def send(data: str) -> None:
        sent.append(data)
        first_send_started.set()
        await release_send.wait()

    writer = ControlMessageWriter(send)
    writer.start()
    try:
        heartbeat = AgentMessage(type="heartbeat", client_id=CLIENT_ID, request_id="heartbeat-1")
        git_result = AgentMessage(type="git_worktree_result", client_id=CLIENT_ID, request_id="git-1")
        terminal_result = AgentMessage(
            type="terminal_attach_result",
            client_id=CLIENT_ID,
            window_id=WINDOW_ID,
            request_id="terminal-1",
        )

        await writer.send(heartbeat)
        await asyncio.wait_for(first_send_started.wait(), timeout=1)
        await writer.send(git_result)
        await writer.send(terminal_result)

        release_send.set()
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [
            heartbeat,
            terminal_result,
            git_result,
        ]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_prioritizes_terminal_output_with_ai_event_fairness() -> None:
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)

    writer = BulkUploadWriter(send, terminal_burst=2)
    writer.start()
    try:
        terminal_1 = _terminal_message(b"one", "terminal-1")
        terminal_2 = _terminal_message(b"two", "terminal-2")
        terminal_3 = _terminal_message(b"three", "terminal-3")
        ai_event = _ai_event("ai-event-1")

        await writer.send_terminal_output(terminal_1)
        await writer.send_terminal_output(terminal_2)
        await writer.send_terminal_output(terminal_3)
        await writer.send_ai_event(ai_event)
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [
            terminal_1,
            terminal_2,
            ai_event,
            terminal_3,
        ]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_prioritizes_status_events_before_agent_records() -> None:
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)

    writer = BulkUploadWriter(send)
    writer.start()
    try:
        ai_event = _ai_event("ai-event-1")
        status_event = _status_event("status-event-1")

        await writer.send_ai_event(ai_event)
        await writer.send_ai_event(status_event)
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [
            status_event,
            ai_event,
        ]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_rotates_terminal_output_between_windows() -> None:
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)

    writer = BulkUploadWriter(send, terminal_burst=10)
    writer.start()
    try:
        busy_1 = _terminal_message(b"busy-1", "busy-1")
        busy_2 = _terminal_message(b"busy-2", "busy-2")
        busy_3 = _terminal_message(b"busy-3", "busy-3")
        other = _terminal_message(b"other", "other", window_id=OTHER_WINDOW_ID)

        await writer.send_terminal_output(busy_1)
        await writer.send_terminal_output(busy_2)
        await writer.send_terminal_output(busy_3)
        await writer.send_terminal_output(other)
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [
            busy_1,
            other,
            busy_2,
            busy_3,
        ]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_prioritizes_recent_input_window_output() -> None:
    first_send_started = asyncio.Event()
    release_first_send = asyncio.Event()
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)
        first_send_started.set()
        await release_first_send.wait()

    writer = BulkUploadWriter(send, terminal_burst=10)
    writer.start()
    try:
        busy_1 = _terminal_message(b"busy-1", "busy-1")
        busy_2 = _terminal_message(b"busy-2", "busy-2")
        busy_3 = _terminal_message(b"busy-3", "busy-3")
        other_stale = _terminal_message(b"other-stale", "other-stale", window_id=OTHER_WINDOW_ID)
        input_response = _terminal_message(
            b"input-response",
            "input-response",
            window_id=OTHER_WINDOW_ID,
        )

        await writer.send_terminal_output(busy_1)
        await asyncio.wait_for(first_send_started.wait(), timeout=1)
        await writer.send_terminal_output(busy_2)
        await writer.send_terminal_output(busy_3)
        await writer.send_terminal_output(other_stale)
        await writer.prioritize_terminal_window(OTHER_WINDOW_ID)
        await writer.send_terminal_output(input_response)

        release_first_send.set()
        await writer.drain()

        sent_messages = [decode_agent_message(data) for data in sent]
        assert sent_messages == [busy_1, input_response, busy_2, other_stale, busy_3]
        assert sent_messages[1].payload["input_priority"] is True
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_splits_large_terminal_output_for_window_fairness() -> None:
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)

    writer = BulkUploadWriter(send, terminal_chunk_bytes=4)
    writer.start()
    try:
        large = _terminal_message(b"abcdefgh", "large")
        other = _terminal_message(b"othr", "other", window_id=OTHER_WINDOW_ID)

        await writer.send_terminal_output(large)
        await writer.send_terminal_output(other)
        await writer.drain()

        sent_messages = [decode_agent_message(data) for data in sent]
        assert [message.window_id for message in sent_messages] == [
            WINDOW_ID,
            OTHER_WINDOW_ID,
            WINDOW_ID,
        ]
        assert b"".join(
            TerminalPayload.model_validate(message.payload).to_bytes()
            for message in sent_messages
            if message.window_id == WINDOW_ID
        ) == b"abcdefgh"
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_preserves_terminal_output_metadata_when_splitting() -> None:
    sent: list[str] = []
    view_id = UUID("22222222-3333-4444-5555-666666666666")

    async def send(data: str) -> None:
        sent.append(data)

    payload = TerminalPayload.from_bytes(WINDOW_ID, b"abcdefgh").model_dump(mode="json")
    payload["view_id"] = str(view_id)
    payload["is_snapshot"] = True
    message = AgentMessage(
        type="terminal_output",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        request_id="large",
        payload=payload,
    )

    writer = BulkUploadWriter(send, terminal_chunk_bytes=4)
    writer.start()
    try:
        await writer.send_terminal_output(message)
        await writer.drain()

        sent_messages = [decode_agent_message(data) for data in sent]
        assert [TerminalPayload.model_validate(item.payload).to_bytes() for item in sent_messages] == [
            b"abcd",
            b"efgh",
        ]
        assert [item.payload["view_id"] for item in sent_messages] == [str(view_id), str(view_id)]
        assert [item.payload["is_snapshot"] for item in sent_messages] == [True, True]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_bulk_upload_writer_blocks_enqueue_when_terminal_output_queue_is_full_until_writer_drains() -> None:
    first_send_started = asyncio.Event()
    release_first_send = asyncio.Event()
    sent: list[str] = []

    async def send(data: str) -> None:
        sent.append(data)
        first_send_started.set()
        await release_first_send.wait()

    writer = BulkUploadWriter(send, terminal_output_maxsize=1)
    writer.start()
    try:
        terminal_1 = _terminal_message(b"one", "terminal-1")
        terminal_2 = _terminal_message(b"two", "terminal-2")
        terminal_3 = _terminal_message(b"three", "terminal-3")

        await writer.send_terminal_output(terminal_1)
        await writer.send_terminal_output(terminal_2)
        await asyncio.wait_for(first_send_started.wait(), timeout=1)

        blocked_enqueue = asyncio.create_task(writer.send_terminal_output(terminal_3))
        await asyncio.sleep(0)

        assert not blocked_enqueue.done()
        assert [decode_agent_message(data) for data in sent] == [terminal_1]

        release_first_send.set()
        await asyncio.wait_for(blocked_enqueue, timeout=1)
        await writer.drain()

        assert [decode_agent_message(data) for data in sent] == [
            terminal_1,
            terminal_2,
            terminal_3,
        ]
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_control_message_writer_raises_outbound_writer_closed_after_close() -> None:
    async def send(data: str) -> None:
        raise AssertionError("send should not be called after close")

    writer = ControlMessageWriter(send)
    writer.start()
    await writer.close()

    with pytest.raises(OutboundWriterClosed):
        await writer.send(AgentMessage(type="heartbeat", client_id=CLIENT_ID))
