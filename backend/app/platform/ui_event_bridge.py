from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from uuid import UUID

from redis import asyncio as aioredis

from app.platform.ui_events import UiEventHub, UiResource

logger = logging.getLogger(__name__)


class RedisUiEventPublisher:
    def __init__(self, redis_client: aioredis.Redis, channel: str) -> None:
        self._redis_client = redis_client
        self._channel = channel

    async def publish_invalidation(
        self,
        resources: Iterable[UiResource],
        *,
        client_id: UUID | None = None,
        window_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        await self._redis_client.publish(
            self._channel,
            json.dumps(
                {
                    "type": "invalidate",
                    "resources": list(resources),
                    "client_id": str(client_id) if client_id is not None else None,
                    "window_id": str(window_id) if window_id is not None else None,
                    "reason": reason,
                },
                separators=(",", ":"),
            ),
        )


async def run_redis_ui_event_bridge(
    ui_event_hub: UiEventHub,
    *,
    redis_url: str,
    channel: str,
    retry_delay_seconds: float = 1.0,
) -> None:
    while True:
        client = aioredis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            health_check_interval=30,
        )
        try:
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(channel)
                await _consume_pubsub_messages(ui_event_hub, pubsub)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("redis ui event bridge disconnected", exc_info=True)
            await asyncio.sleep(retry_delay_seconds)
        finally:
            await client.aclose()


async def _consume_pubsub_messages(ui_event_hub: UiEventHub, pubsub: object) -> None:
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is None:
            await asyncio.sleep(0)
            continue
        if message.get("type") != "message":
            continue
        await publish_local_ui_event_message(ui_event_hub, message.get("data"))


async def publish_local_ui_event_message(ui_event_hub: UiEventHub, raw_message: object) -> None:
    if not isinstance(raw_message, str):
        return
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict) or payload.get("type") != "invalidate":
        return
    resources = payload.get("resources")
    if not isinstance(resources, list) or not all(isinstance(resource, str) for resource in resources):
        return
    await ui_event_hub.publish_invalidation(
        resources,
        client_id=_uuid_or_none(payload.get("client_id")),
        window_id=_uuid_or_none(payload.get("window_id")),
        reason=payload.get("reason") if isinstance(payload.get("reason"), str) else None,
    )


def _uuid_or_none(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
