from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from redis import asyncio as aioredis
from redis.exceptions import ResponseError

from app.client_agent.ai_events import ManagedAiEvent
from app.config import get_settings


class AgentEventQueueUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentEventQueueConfig:
    redis_url: str
    stream_key: str
    dead_letter_stream_key: str
    consumer_group: str
    stream_maxlen: int
    worker_batch_size: int
    block_ms: int
    claim_idle_ms: int
    max_deliveries: int
    redis_timeout_seconds: float


@dataclass(frozen=True)
class QueuedAgentEvent:
    message_id: str
    event: ManagedAiEvent
    enqueued_at: str | None


def queue_config_from_settings() -> AgentEventQueueConfig | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    return AgentEventQueueConfig(
        redis_url=settings.redis_url,
        stream_key=settings.agent_event_stream_key,
        dead_letter_stream_key=settings.agent_event_dead_letter_stream_key,
        consumer_group=settings.agent_event_consumer_group,
        stream_maxlen=settings.agent_event_stream_maxlen,
        worker_batch_size=settings.agent_event_worker_batch_size,
        block_ms=settings.agent_event_worker_block_ms,
        claim_idle_ms=settings.agent_event_claim_idle_ms,
        max_deliveries=settings.agent_event_max_deliveries,
        redis_timeout_seconds=settings.agent_event_redis_timeout_seconds,
    )


def create_redis_client(config: AgentEventQueueConfig) -> aioredis.Redis:
    return aioredis.Redis.from_url(
        config.redis_url,
        decode_responses=True,
        socket_timeout=config.redis_timeout_seconds,
        socket_connect_timeout=config.redis_timeout_seconds,
    )


def create_worker_redis_client(config: AgentEventQueueConfig) -> aioredis.Redis:
    return aioredis.Redis.from_url(
        config.redis_url,
        decode_responses=True,
        socket_timeout=_worker_socket_timeout_seconds(config),
        socket_connect_timeout=config.redis_timeout_seconds,
    )


def _worker_socket_timeout_seconds(config: AgentEventQueueConfig) -> float:
    return max(config.redis_timeout_seconds, (config.block_ms / 1000) + 1.0)


async def enqueue_managed_agent_event(
    event: ManagedAiEvent,
    *,
    redis_client: aioredis.Redis | None = None,
    config: AgentEventQueueConfig | None = None,
) -> str | None:
    config = config or queue_config_from_settings()
    if config is None:
        return None
    owns_client = redis_client is None
    client = redis_client or create_redis_client(config)
    try:
        message_id = await client.xadd(
            config.stream_key,
            _event_fields(event),
        )
        return str(message_id)
    except Exception as exc:
        raise AgentEventQueueUnavailable("agent event queue is unavailable") from exc
    finally:
        if owns_client:
            await client.aclose()


async def ensure_agent_event_consumer_group(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
) -> None:
    try:
        await redis_client.xgroup_create(
            config.stream_key,
            config.consumer_group,
            id="0-0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def read_agent_event_batch(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    *,
    consumer_name: str,
    count: int | None = None,
    block_ms: int | None = None,
) -> list[QueuedAgentEvent]:
    effective_block_ms = config.block_ms if block_ms is None else block_ms
    block_arg = effective_block_ms if effective_block_ms > 0 else None
    raw = await redis_client.xreadgroup(
        config.consumer_group,
        consumer_name,
        streams={config.stream_key: ">"},
        count=count or config.worker_batch_size,
        block=block_arg,
    )
    return _decode_stream_response(raw)


async def claim_stale_agent_events(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    *,
    consumer_name: str,
) -> list[QueuedAgentEvent]:
    raw = await redis_client.xautoclaim(
        config.stream_key,
        config.consumer_group,
        consumer_name,
        min_idle_time=config.claim_idle_ms,
        start_id="0-0",
        count=config.worker_batch_size,
    )
    messages = raw[1] if isinstance(raw, list | tuple) and len(raw) >= 2 else []
    return _decode_messages(messages)


async def read_recent_agent_event_tail(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    *,
    count: int | None = None,
) -> list[QueuedAgentEvent]:
    raw = await redis_client.xrevrange(
        config.stream_key,
        max="+",
        min="-",
        count=count or config.worker_batch_size,
    )
    messages = list(reversed(raw or []))
    return _decode_messages(messages)


async def ack_agent_events(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    message_ids: list[str],
) -> None:
    if message_ids:
        await redis_client.xack(config.stream_key, config.consumer_group, *message_ids)
        await redis_client.xdel(config.stream_key, *message_ids)


async def delivery_count(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    message_id: str,
) -> int:
    pending = await redis_client.xpending_range(
        config.stream_key,
        config.consumer_group,
        min=message_id,
        max=message_id,
        count=1,
    )
    if not pending:
        return 1
    entry = pending[0]
    if isinstance(entry, dict):
        value = entry.get("times_delivered") or entry.get("delivery_count")
    else:
        value = getattr(entry, "times_delivered", None) or getattr(entry, "delivery_count", None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


async def move_agent_event_to_dead_letter(
    redis_client: aioredis.Redis,
    config: AgentEventQueueConfig,
    queued_event: QueuedAgentEvent,
    *,
    error: str,
    deliveries: int,
) -> None:
    fields = _event_fields(queued_event.event)
    fields.update(
        {
            "source_message_id": queued_event.message_id,
            "dead_lettered_at": datetime.now(UTC).isoformat(),
            "deliveries": str(deliveries),
            "error": error[:4000],
        }
    )
    await redis_client.xadd(
        config.dead_letter_stream_key,
        fields,
        maxlen=config.stream_maxlen,
        approximate=True,
    )
    await ack_agent_events(redis_client, config, [queued_event.message_id])


def default_consumer_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _event_fields(event: ManagedAiEvent) -> dict[str, str]:
    return {
        "client_id": str(event.client_id),
        "window_id": str(event.window_id),
        "provider": event.provider,
        "source_path": event.source_path or "",
        "offset": "" if event.offset is None else str(event.offset),
        "cursor": "" if event.cursor is None else json.dumps(jsonable_encoder(event.cursor)),
        "project_path": event.project_path or "",
        "payload": json.dumps(jsonable_encoder(event.payload), separators=(",", ":")),
        "enqueued_at": datetime.now(UTC).isoformat(),
    }


def _decode_stream_response(raw: Any) -> list[QueuedAgentEvent]:
    messages: list[Any] = []
    for _stream_key, stream_messages in raw or []:
        messages.extend(stream_messages)
    return _decode_messages(messages)


def _decode_messages(messages: Any) -> list[QueuedAgentEvent]:
    decoded: list[QueuedAgentEvent] = []
    for message_id, fields in messages or []:
        decoded.append(_queued_event_from_fields(str(message_id), fields))
    return decoded


def _queued_event_from_fields(message_id: str, fields: dict[str, Any]) -> QueuedAgentEvent:
    from uuid import UUID

    payload = json.loads(fields.get("payload") or "{}")
    if not isinstance(payload, dict):
        raise ValueError("queued agent event payload must be an object")
    offset = fields.get("offset") or None
    raw_cursor = fields.get("cursor") or None
    cursor = json.loads(raw_cursor) if raw_cursor is not None else None
    event = ManagedAiEvent(
        client_id=UUID(str(fields["client_id"])),
        window_id=UUID(str(fields["window_id"])),
        provider=str(fields["provider"]),
        source_path=fields.get("source_path") or None,
        offset=int(offset) if offset is not None else None,
        cursor=cursor,
        project_path=fields.get("project_path") or None,
        payload=payload,
    )
    return QueuedAgentEvent(
        message_id=message_id,
        event=event,
        enqueued_at=fields.get("enqueued_at") or None,
    )
