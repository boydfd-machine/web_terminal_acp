from __future__ import annotations

from uuid import UUID

import pytest

from app.client_agent.ai_events import managed_event_from_payload
from app.contexts.activity.application import agent_event_worker
from app.contexts.activity.application.agent_event_queue import (
    AgentEventQueueConfig,
    _worker_socket_timeout_seconds,
    enqueue_managed_agent_event,
    move_agent_event_to_dead_letter,
    read_agent_event_batch,
)


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")


@pytest.fixture(autouse=True)
def clear_worker_recent_tail_cache():
    agent_event_worker._recent_tail_seen_ids.clear()
    yield
    agent_event_worker._recent_tail_seen_ids.clear()


class FakeRedisStream:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.pending: dict[str, int] = {}
        self.acked: list[str] = []
        self.deleted: list[str] = []
        self.xadd_kwargs: list[dict[str, object]] = []
        self.groups: set[tuple[str, str]] = set()
        self.xreadgroup_blocks: list[int | None] = []

    async def xgroup_create(self, name, groupname, id="0-0", mkstream=False):  # noqa: ANN001, A002
        self.groups.add((name, groupname))
        if mkstream:
            self.streams.setdefault(name, [])
        return True

    async def xadd(self, name, fields, **_kwargs):  # noqa: ANN001
        self.xadd_kwargs.append(dict(_kwargs))
        message_id = f"{len(self.streams.setdefault(name, [])) + 1}-0"
        self.streams[name].append((message_id, dict(fields)))
        return message_id

    async def xreadgroup(self, groupname, consumername, streams, count=None, block=None, noack=False):  # noqa: ANN001
        self.xreadgroup_blocks.append(block)
        stream_name = next(iter(streams))
        messages = [
            (message_id, fields)
            for message_id, fields in self.streams.get(stream_name, [])
            if message_id not in self.pending and message_id not in self.acked
        ][: count or 100]
        for message_id, _fields in messages:
            self.pending[message_id] = 1
        return [(stream_name, messages)] if messages else []

    async def xack(self, name, groupname, *ids):  # noqa: ANN001, A002
        self.acked.extend(str(message_id) for message_id in ids if str(message_id) in self.pending)
        for message_id in ids:
            self.pending.pop(str(message_id), None)
        return len(ids)

    async def xdel(self, name, *ids):  # noqa: ANN001, A002
        ids_to_delete = [str(message_id) for message_id in ids]
        self.deleted.extend(ids_to_delete)
        id_set = set(ids_to_delete)
        self.streams[name] = [
            (message_id, fields)
            for message_id, fields in self.streams.get(name, [])
            if message_id not in id_set
        ]
        return len(ids_to_delete)

    async def xpending_range(self, name, groupname, min, max, count, **_kwargs):  # noqa: ANN001, A002
        if min in self.pending:
            return [{"message_id": min, "times_delivered": self.pending[min]}]
        return []

    async def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id="0-0", count=None, justid=False):  # noqa: ANN001
        messages = []
        for message_id, fields in self.streams.get(name, []):
            if message_id not in self.pending or message_id in self.acked:
                continue
            self.pending[message_id] += 1
            messages.append((message_id, fields))
            if len(messages) >= (count or 100):
                break
        return ["0-0", messages, []]

    async def xrevrange(self, name, max="+", min="-", count=None):  # noqa: ANN001, A002
        messages = list(reversed(self.streams.get(name, [])))
        return messages[: count or 100]

    async def aclose(self) -> None:
        return None


def _config(*, worker_batch_size: int = 10, max_deliveries: int = 2) -> AgentEventQueueConfig:
    return AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=worker_batch_size,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=max_deliveries,
        redis_timeout_seconds=0.1,
    )


def _event(*, text: str = "queued hello"):
    payload = {
        "client_id": str(CLIENT_ID),
        "virtual_window_id": str(WINDOW_ID),
        "agentId": "cursor-agent",
        "blob_id": "blob-1",
        "role": "assistant",
        "text": text,
    }
    event = managed_event_from_payload(
        CLIENT_ID,
        WINDOW_ID,
        "cursor_cli",
        payload,
        source_path="/tmp/session.jsonl",
        offset=10,
        cursor=11,
        project_path="/workspace/project",
    )
    assert event is not None
    return event


def test_worker_socket_timeout_covers_blocking_read_window() -> None:
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=1000,
        claim_idle_ms=1,
        max_deliveries=2,
        redis_timeout_seconds=0.2,
    )

    assert _worker_socket_timeout_seconds(config) == 2.0


@pytest.mark.asyncio
async def test_enqueue_and_read_agent_event_round_trips_payload_and_cursor() -> None:
    redis = FakeRedisStream()
    config = _config()
    event = _event()

    message_id = await enqueue_managed_agent_event(event, redis_client=redis, config=config)
    batch = await read_agent_event_batch(redis, config, consumer_name="worker-1")

    assert message_id == "1-0"
    assert len(batch) == 1
    queued = batch[0]
    assert queued.message_id == "1-0"
    assert queued.event.client_id == event.client_id
    assert queued.event.window_id == event.window_id
    assert queued.event.provider == "cursor_cli"
    assert queued.event.source_path == "/tmp/session.jsonl"
    assert queued.event.offset == 10
    assert queued.event.cursor == 11
    assert queued.event.project_path == "/workspace/project"
    assert queued.event.payload["text"] == "queued hello"
    assert redis.xadd_kwargs == [{}]


@pytest.mark.asyncio
async def test_enqueue_does_not_trim_unprocessed_events_by_maxlen() -> None:
    redis = FakeRedisStream()
    config = _config()

    await enqueue_managed_agent_event(_event(), redis_client=redis, config=config)

    assert redis.xadd_kwargs == [{}]


@pytest.mark.asyncio
async def test_read_agent_event_batch_treats_zero_block_ms_as_nonblocking() -> None:
    redis = FakeRedisStream()
    config = _config()
    await enqueue_managed_agent_event(_event(), redis_client=redis, config=config)

    await read_agent_event_batch(redis, config, consumer_name="worker-1", block_ms=0)

    assert redis.xreadgroup_blocks == [None]


@pytest.mark.asyncio
async def test_dead_letter_copies_event_and_acks_source_message() -> None:
    redis = FakeRedisStream()
    config = _config()
    event = _event()
    await enqueue_managed_agent_event(event, redis_client=redis, config=config)
    queued = (await read_agent_event_batch(redis, config, consumer_name="worker-1"))[0]

    await move_agent_event_to_dead_letter(
        redis,
        config,
        queued,
        error="boom",
        deliveries=3,
    )

    assert redis.acked == ["1-0"]
    assert redis.deleted == ["1-0"]
    dead_letter_fields = redis.streams[config.dead_letter_stream_key][0][1]
    assert dead_letter_fields["source_message_id"] == "1-0"
    assert dead_letter_fields["deliveries"] == "3"
    assert dead_letter_fields["error"] == "boom"


@pytest.mark.asyncio
async def test_worker_leaves_retryable_failure_pending(monkeypatch) -> None:
    redis = FakeRedisStream()
    config = _config()
    await enqueue_managed_agent_event(_event(), redis_client=redis, config=config)

    async def fail_process(*_args, **_kwargs):
        raise RuntimeError("transient")

    monkeypatch.setattr(agent_event_worker, "process_managed_agent_event_with_session_factory", fail_process)

    processed = await agent_event_worker.process_agent_event_queue_once(
        lambda: None,
        redis_client=redis,
        config=config,
        consumer_name="worker-1",
        prefer_claimed=False,
    )

    assert processed == 0
    assert redis.acked == []
    assert redis.pending == {"1-0": 1}


@pytest.mark.asyncio
async def test_worker_dead_letters_after_max_deliveries(monkeypatch) -> None:
    redis = FakeRedisStream()
    config = _config()
    await enqueue_managed_agent_event(_event(), redis_client=redis, config=config)
    first = await read_agent_event_batch(redis, config, consumer_name="worker-1")
    assert first[0].message_id == "1-0"

    async def fail_process(*_args, **_kwargs):
        raise RuntimeError("permanent")

    monkeypatch.setattr(agent_event_worker, "process_managed_agent_event_with_session_factory", fail_process)

    processed = await agent_event_worker.process_agent_event_queue_once(
        lambda: None,
        redis_client=redis,
        config=config,
        consumer_name="worker-2",
    )

    assert processed == 0
    assert redis.acked == ["1-0"]
    dead_letter_fields = redis.streams[config.dead_letter_stream_key][0][1]
    assert dead_letter_fields["source_message_id"] == "1-0"
    assert dead_letter_fields["error"] == "permanent"


@pytest.mark.asyncio
async def test_worker_does_not_starve_new_events_behind_retryable_pending_failure(monkeypatch) -> None:
    redis = FakeRedisStream()
    config = _config(worker_batch_size=1, max_deliveries=10)
    await enqueue_managed_agent_event(_event(text="bad pending"), redis_client=redis, config=config)
    first = await read_agent_event_batch(redis, config, consumer_name="worker-1")
    assert first[0].message_id == "1-0"
    await enqueue_managed_agent_event(_event(text="new good"), redis_client=redis, config=config)
    processed_payloads: list[str] = []

    async def process_by_payload(_session_factory, event, **_kwargs):
        processed_payloads.append(event.payload["text"])
        if event.payload["text"] == "bad pending":
            raise RuntimeError("stale pending failure")

    monkeypatch.setattr(agent_event_worker, "process_managed_agent_event_with_session_factory", process_by_payload)

    processed = await agent_event_worker.process_agent_event_queue_once(
        lambda: None,
        redis_client=redis,
        config=config,
        consumer_name="worker-2",
    )

    assert processed == 1
    assert processed_payloads == ["new good", "bad pending"]
    assert redis.acked == ["2-0"]
    assert redis.deleted == ["2-0"]
    assert redis.pending == {"1-0": 2}


@pytest.mark.asyncio
async def test_worker_processes_recent_tail_event_even_when_fifo_backlog_is_older(monkeypatch) -> None:
    redis = FakeRedisStream()
    config = _config(worker_batch_size=1, max_deliveries=10)
    await enqueue_managed_agent_event(_event(text="old backlog"), redis_client=redis, config=config)
    await enqueue_managed_agent_event(_event(text="latest good"), redis_client=redis, config=config)
    processed_payloads: list[str] = []

    async def process_by_payload(_session_factory, event, **_kwargs):
        processed_payloads.append(event.payload["text"])
        if event.payload["text"] == "old backlog":
            raise RuntimeError("old backlog failure")

    monkeypatch.setattr(agent_event_worker, "process_managed_agent_event_with_session_factory", process_by_payload)

    processed = await agent_event_worker.process_agent_event_queue_once(
        lambda: None,
        redis_client=redis,
        config=config,
        consumer_name="worker-1",
        prefer_claimed=False,
    )

    assert processed == 1
    assert processed_payloads == ["latest good", "old backlog"]
    assert redis.acked == []
    assert redis.pending == {"1-0": 1}
