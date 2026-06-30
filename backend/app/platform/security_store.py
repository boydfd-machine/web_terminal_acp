from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic, time
from typing import Any

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "web-terminal-acp:security"
_REDIS_TIMEOUT_SECONDS = 0.05
_REDIS_RETRY_AFTER_SECONDS = 30.0
_EVENT_STREAM = f"{_KEY_PREFIX}:events"
_REDIS_UNAVAILABLE = object()


@dataclass(frozen=True)
class CounterState:
    count: int
    retry_after_seconds: int


class InMemorySecurityStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counters: dict[str, tuple[int, float]] = {}
        self._captchas: dict[str, tuple[dict[str, Any], float]] = {}
        self.events: list[dict[str, Any]] = []

    async def increment_counter(self, key: str, ttl_seconds: int) -> CounterState:
        async with self._lock:
            now = monotonic()
            self._prune(now)
            count, expires_at = self._counters.get(key, (0, now + ttl_seconds))
            if now >= expires_at:
                count = 0
                expires_at = now + ttl_seconds
            count += 1
            self._counters[key] = (count, expires_at)
            return CounterState(count=count, retry_after_seconds=max(1, int(expires_at - now)))

    async def read_counter(self, key: str) -> CounterState:
        async with self._lock:
            now = monotonic()
            self._prune(now)
            current = self._counters.get(key)
            if current is None:
                return CounterState(count=0, retry_after_seconds=0)
            count, expires_at = current
            return CounterState(count=count, retry_after_seconds=max(1, int(expires_at - now)))

    async def clear_counter(self, key: str) -> None:
        async with self._lock:
            self._counters.pop(key, None)

    async def set_captcha(self, captcha_id: str, value: dict[str, Any], ttl_seconds: int) -> None:
        async with self._lock:
            self._captchas[captcha_id] = (value, monotonic() + ttl_seconds)

    async def pop_captcha(self, captcha_id: str) -> dict[str, Any] | None:
        async with self._lock:
            now = monotonic()
            self._prune(now)
            current = self._captchas.pop(captcha_id, None)
            if current is None:
                return None
            value, expires_at = current
            return value if now < expires_at else None

    async def record_event(self, event: dict[str, Any]) -> None:
        async with self._lock:
            self.events.append(event)
            del self.events[:-1000]

    async def clear(self) -> None:
        async with self._lock:
            self._counters.clear()
            self._captchas.clear()
            self.events.clear()

    def _prune(self, now: float) -> None:
        self._counters = {
            key: value for key, value in self._counters.items() if value[1] > now
        }
        self._captchas = {
            key: value for key, value in self._captchas.items() if value[1] > now
        }


class SecurityStore:
    def __init__(self) -> None:
        self._local = InMemorySecurityStore()
        self._redis: AsyncRedis | None = None
        self._redis_url: str | None = None
        self._redis_disabled_until = 0.0

    async def increment_counter(self, scope: str, identity: str, ttl_seconds: int) -> CounterState:
        key = _counter_key(scope, identity)

        async def operation(client: AsyncRedis) -> CounterState:
            count = int(await client.incr(key))
            if count == 1:
                await client.expire(key, ttl_seconds)
                retry_after = ttl_seconds
            else:
                ttl = int(await client.ttl(key))
                retry_after = ttl_seconds if ttl < 0 else ttl
            return CounterState(count=count, retry_after_seconds=max(1, retry_after))

        result = await self._run_redis(operation)
        if result is not _REDIS_UNAVAILABLE:
            return result
        return await self._local.increment_counter(key, ttl_seconds)

    async def read_counter(self, scope: str, identity: str) -> CounterState:
        key = _counter_key(scope, identity)

        async def operation(client: AsyncRedis) -> CounterState:
            raw_count = await client.get(key)
            if raw_count is None:
                return CounterState(count=0, retry_after_seconds=0)
            ttl = int(await client.ttl(key))
            return CounterState(count=int(raw_count), retry_after_seconds=max(1, ttl))

        result = await self._run_redis(operation)
        if result is not _REDIS_UNAVAILABLE:
            return result
        return await self._local.read_counter(key)

    async def clear_counter(self, scope: str, identity: str) -> None:
        key = _counter_key(scope, identity)

        async def operation(client: AsyncRedis) -> None:
            await client.delete(key)

        if await self._run_redis(operation) is _REDIS_UNAVAILABLE:
            await self._local.clear_counter(key)

    async def set_captcha(self, captcha_id: str, value: dict[str, Any], ttl_seconds: int) -> None:
        key = _captcha_key(captcha_id)
        payload = json.dumps(jsonable_encoder(value), separators=(",", ":"))

        async def operation(client: AsyncRedis) -> None:
            await client.set(key, payload, ex=ttl_seconds)

        if await self._run_redis(operation) is _REDIS_UNAVAILABLE:
            await self._local.set_captcha(captcha_id, value, ttl_seconds)

    async def pop_captcha(self, captcha_id: str) -> dict[str, Any] | None:
        key = _captcha_key(captcha_id)

        async def operation(client: AsyncRedis) -> dict[str, Any] | None:
            pipeline = client.pipeline(transaction=True)
            pipeline.get(key)
            pipeline.delete(key)
            raw, _deleted = await pipeline.execute()
            if raw is None:
                return None
            try:
                value = json.loads(_raw_text(raw))
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None

        result = await self._run_redis(operation)
        if result is not _REDIS_UNAVAILABLE:
            return result
        return await self._local.pop_captcha(captcha_id)

    async def record_event(self, event: dict[str, Any]) -> None:
        payload = {
            **event,
            "created_at": event.get("created_at") or time(),
        }

        async def operation(client: AsyncRedis) -> None:
            await client.xadd(
                _EVENT_STREAM,
                {"event": json.dumps(jsonable_encoder(payload), separators=(",", ":"))},
                maxlen=10000,
                approximate=True,
            )

        if await self._run_redis(operation) is _REDIS_UNAVAILABLE:
            await self._local.record_event(payload)

    async def clear_local(self) -> None:
        await self._local.clear()

    async def _run_redis(self, operation):
        client = self._get_redis_client()
        if client is None:
            return _REDIS_UNAVAILABLE
        try:
            return await operation(client)
        except (OSError, RedisError):
            self._disable_redis_temporarily()
            logger.warning("redis security operation failed; falling back to local store", exc_info=True)
            return _REDIS_UNAVAILABLE

    def _get_redis_client(self) -> AsyncRedis | None:
        url = get_settings().redis_url
        if not url:
            return None
        if monotonic() < self._redis_disabled_until:
            return None
        if self._redis is not None and self._redis_url == url:
            return self._redis
        self._redis_url = url
        self._redis = AsyncRedis.from_url(
            url,
            decode_responses=True,
            socket_timeout=_REDIS_TIMEOUT_SECONDS,
            socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
        )
        return self._redis

    def _disable_redis_temporarily(self) -> None:
        self._redis = None
        self._redis_disabled_until = monotonic() + _REDIS_RETRY_AFTER_SECONDS


_store = SecurityStore()


def get_security_store() -> SecurityStore:
    return _store


async def reset_security_store_for_tests() -> None:
    await _store.clear_local()


def _counter_key(scope: str, identity: str) -> str:
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:counter:{scope}:{digest}"


def _captcha_key(captcha_id: str) -> str:
    return f"{_KEY_PREFIX}:captcha:{captcha_id}"


def _raw_text(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return raw if isinstance(raw, str) else str(raw)
