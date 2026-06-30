from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from elastic_transport import TransportError
from elasticsearch import ApiError, AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.agent_event_processor import (
    process_managed_agent_event_with_session_factory,
)
from app.contexts.activity.application.agent_event_queue import (
    AgentEventQueueConfig,
    QueuedAgentEvent,
    ack_agent_events,
    claim_stale_agent_events,
    create_worker_redis_client,
    default_consumer_name,
    delivery_count,
    ensure_agent_event_consumer_group,
    move_agent_event_to_dead_letter,
    queue_config_from_settings,
    read_agent_event_batch,
    read_recent_agent_event_tail,
)
from app.config import get_settings
from app.db import SessionLocal
from app.platform.search_index import ensure_indexes, get_es_client
from app.platform.ui_event_bridge import RedisUiEventPublisher
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
RECENT_TAIL_SEEN_LIMIT = 10_000
_recent_tail_seen_ids: OrderedDict[str, None] = OrderedDict()


async def process_agent_event_queue_once(
    session_factory: SessionFactory,
    *,
    redis_client,
    config: AgentEventQueueConfig,
    consumer_name: str,
    es_client: AsyncElasticsearch | None = None,
    ui_event_hub: UiEventHub | None = None,
    prefer_claimed: bool = True,
) -> int:
    queued_events = (
        await claim_stale_agent_events(redis_client, config, consumer_name=consumer_name)
        if prefer_claimed
        else []
    )
    recent_events = _filter_recent_tail_events(
        await read_recent_agent_event_tail(
            redis_client,
            config,
            count=config.worker_batch_size,
        )
    )

    if queued_events or recent_events:
        new_events = await read_agent_event_batch(
            redis_client,
            config,
            consumer_name=consumer_name,
            count=config.worker_batch_size,
            block_ms=0,
        )
    else:
        new_events = await read_agent_event_batch(
            redis_client,
            config,
            consumer_name=consumer_name,
        )

    if queued_events:
        queued_events = _dedupe_queued_events([*recent_events, *new_events, *queued_events])
    else:
        queued_events = _dedupe_queued_events([*recent_events, *new_events])

    if not queued_events:
        return 0

    processed_ids: list[str] = []
    recent_event_ids = {queued_event.message_id for queued_event in recent_events}
    attempted_tail_events: list[QueuedAgentEvent] = []
    for queued_event in queued_events:
        if queued_event.message_id in recent_event_ids:
            attempted_tail_events.append(queued_event)
        if await _process_one(
            session_factory,
            redis_client=redis_client,
            config=config,
            queued_event=queued_event,
            es_client=es_client,
            ui_event_hub=ui_event_hub,
        ):
            processed_ids.append(queued_event.message_id)
    _remember_recent_tail_events(attempted_tail_events)
    await ack_agent_events(redis_client, config, processed_ids)
    return len(processed_ids)


def _filter_recent_tail_events(queued_events: list[QueuedAgentEvent]) -> list[QueuedAgentEvent]:
    return [queued_event for queued_event in queued_events if queued_event.message_id not in _recent_tail_seen_ids]


def _remember_recent_tail_events(queued_events: list[QueuedAgentEvent]) -> None:
    for queued_event in queued_events:
        _recent_tail_seen_ids[queued_event.message_id] = None
        _recent_tail_seen_ids.move_to_end(queued_event.message_id)
    while len(_recent_tail_seen_ids) > RECENT_TAIL_SEEN_LIMIT:
        _recent_tail_seen_ids.popitem(last=False)


def _dedupe_queued_events(queued_events: list[QueuedAgentEvent]) -> list[QueuedAgentEvent]:
    seen: set[str] = set()
    deduped: list[QueuedAgentEvent] = []
    for queued_event in queued_events:
        if queued_event.message_id in seen:
            continue
        seen.add(queued_event.message_id)
        deduped.append(queued_event)
    return deduped


async def run_agent_event_worker_loop(
    session_factory: SessionFactory = SessionLocal,
    *,
    es_client: AsyncElasticsearch | None = None,
    ui_event_hub: UiEventHub | None = None,
    config: AgentEventQueueConfig | None = None,
    consumer_name: str | None = None,
) -> None:
    config = config or queue_config_from_settings()
    if config is None:
        raise RuntimeError("REDIS_URL is required for agent event worker")

    client = create_worker_redis_client(config)
    close_es_client = es_client is None
    es_client = es_client or get_es_client()
    ui_event_hub = ui_event_hub or RedisUiEventPublisher(
        client,
        get_settings().ui_event_redis_channel,
    )
    consumer_name = consumer_name or default_consumer_name()
    try:
        await ensure_agent_event_consumer_group(client, config)
        await _ensure_search_indexes(es_client)
        while True:
            try:
                await process_agent_event_queue_once(
                    session_factory,
                    redis_client=client,
                    config=config,
                    consumer_name=consumer_name,
                    es_client=es_client,
                    ui_event_hub=ui_event_hub,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("agent event worker iteration failed")
                await asyncio.sleep(1.0)
    finally:
        await client.aclose()
        if close_es_client and es_client is not None:
            await es_client.close()


async def _process_one(
    session_factory: SessionFactory,
    *,
    redis_client,
    config: AgentEventQueueConfig,
    queued_event: QueuedAgentEvent,
    es_client: AsyncElasticsearch | None,
    ui_event_hub: UiEventHub | None,
) -> bool:
    try:
        await process_managed_agent_event_with_session_factory(
            session_factory,
            queued_event.event,
            es_client=es_client,
            ui_event_hub=ui_event_hub,
        )
        return True
    except Exception as exc:
        deliveries = await delivery_count(redis_client, config, queued_event.message_id)
        if deliveries >= config.max_deliveries:
            logger.exception(
                "moving failed agent event to dead-letter stream",
                extra={
                    "client_id": str(queued_event.event.client_id),
                    "window_id": str(queued_event.event.window_id),
                    "message_id": queued_event.message_id,
                    "deliveries": deliveries,
                },
            )
            await move_agent_event_to_dead_letter(
                redis_client,
                config,
                queued_event,
                error=str(exc),
                deliveries=deliveries,
            )
            return False
        logger.warning(
            "agent event processing failed; leaving message pending",
            extra={
                "client_id": str(queued_event.event.client_id),
                "window_id": str(queued_event.event.window_id),
                "message_id": queued_event.message_id,
                "deliveries": deliveries,
            },
            exc_info=True,
        )
        return False


async def _ensure_search_indexes(es_client: AsyncElasticsearch | None) -> None:
    if es_client is None:
        return
    try:
        await ensure_indexes(es_client)
    except (ApiError, TransportError):
        logger.warning("agent event worker search indexes are not ready", exc_info=True)


def main() -> None:
    from app.platform.logging_config import configure_logging

    configure_logging()
    asyncio.run(run_agent_event_worker_loop())


if __name__ == "__main__":
    main()
