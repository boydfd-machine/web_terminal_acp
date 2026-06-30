from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from hashlib import sha256
from time import monotonic
from typing import Any

from fastapi.encoders import jsonable_encoder
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "web-terminal-acp:cache"
_REDIS_RETRY_AFTER_SECONDS = 30.0
_REDIS_TIMEOUT_SECONDS = 0.05

_redis_client: Redis | None = None
_async_redis_client: AsyncRedis | None = None
_redis_url: str | None = None
_async_redis_url: str | None = None
_redis_disabled_until = 0.0
_sync_event_loop_warning_logged = False


def enabled() -> bool:
    return bool(get_settings().redis_url)


def cache_key(namespace: str, key_parts: object) -> str:
    encoded = json.dumps(
        jsonable_encoder(key_parts),
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = sha256(encoded.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:{namespace}:{digest}"


def get_json(namespace: str, key_parts: object) -> dict[str, Any] | None:
    key = cache_key(namespace, key_parts)

    def operation(client: Redis) -> dict[str, Any] | None:
        raw = client.get(key)
        if raw is None:
            return None
        try:
            value = _json_value(raw)
        except json.JSONDecodeError:
            client.delete(key)
            return None
        return value if isinstance(value, dict) else None

    return _run(operation)


async def get_json_async(namespace: str, key_parts: object) -> dict[str, Any] | None:
    key = cache_key(namespace, key_parts)

    async def operation(client: AsyncRedis) -> dict[str, Any] | None:
        raw = await client.get(key)
        if raw is None:
            return None
        try:
            value = _json_value(raw)
        except json.JSONDecodeError:
            await client.delete(key)
            return None
        return value if isinstance(value, dict) else None

    return await _run_async(operation)


def set_json(namespace: str, key_parts: object, value: dict[str, Any], *, ttl_seconds: int) -> bool:
    key = cache_key(namespace, key_parts)
    return set_json_key(key, value, ttl_seconds=ttl_seconds)


def set_indexed_json(
    namespace: str,
    key_parts: object,
    value: dict[str, Any],
    *,
    resources: frozenset[str],
    client_id: str | None,
    ttl_seconds: int,
) -> bool:
    key = cache_key(namespace, key_parts)
    payload = json.dumps(jsonable_encoder(value), separators=(",", ":"))

    def operation(client: Redis) -> bool:
        pipeline = client.pipeline()
        pipeline.set(key, payload, ex=ttl_seconds)
        for index_key in _index_keys(namespace, resources, client_id):
            pipeline.sadd(index_key, key)
            pipeline.expire(index_key, ttl_seconds)
        pipeline.execute()
        return True

    return _run(operation) is True


async def set_indexed_json_async(
    namespace: str,
    key_parts: object,
    value: dict[str, Any],
    *,
    resources: frozenset[str],
    client_id: str | None,
    ttl_seconds: int,
) -> bool:
    key = cache_key(namespace, key_parts)
    payload = json.dumps(jsonable_encoder(value), separators=(",", ":"))

    async def operation(client: AsyncRedis) -> bool:
        pipeline = client.pipeline()
        pipeline.set(key, payload, ex=ttl_seconds)
        for index_key in _index_keys(namespace, resources, client_id):
            pipeline.sadd(index_key, key)
            pipeline.expire(index_key, ttl_seconds)
        await pipeline.execute()
        return True

    return await _run_async(operation) is True


def set_json_key(key: str, value: dict[str, Any], *, ttl_seconds: int) -> bool:
    payload = json.dumps(jsonable_encoder(value), separators=(",", ":"))

    def operation(client: Redis) -> bool:
        client.set(key, payload, ex=ttl_seconds)
        return True

    return _run(operation) is True


def delete_indexed(namespace: str, resources: set[str], *, client_id: str | None) -> None:
    keys = _indexed_data_keys(namespace, resources, client_id=client_id)
    delete_keys(list(keys))


async def delete_indexed_async(namespace: str, resources: set[str], *, client_id: str | None) -> None:
    keys = await _indexed_data_keys_async(namespace, resources, client_id=client_id)
    await delete_keys_async(list(keys))


def expire_indexed_json(
    namespace: str,
    resources: set[str],
    *,
    client_id: str | None,
    created_at: float,
    ttl_seconds: int,
) -> None:
    keys = _indexed_data_keys(namespace, resources, client_id=client_id)
    if not keys:
        return

    def operation(client: Redis) -> None:
        pipeline = client.pipeline()
        for key in keys:
            raw = client.get(key)
            if raw is None:
                continue
            try:
                value = _json_value(raw)
            except json.JSONDecodeError:
                pipeline.delete(key)
                continue
            if not isinstance(value, dict):
                pipeline.delete(key)
                continue
            value["created_at"] = created_at
            pipeline.set(
                key,
                json.dumps(jsonable_encoder(value), separators=(",", ":")),
                ex=ttl_seconds,
            )
        pipeline.execute()

    _run(operation)


async def expire_indexed_json_async(
    namespace: str,
    resources: set[str],
    *,
    client_id: str | None,
    created_at: float,
    ttl_seconds: int,
) -> None:
    keys = await _indexed_data_keys_async(namespace, resources, client_id=client_id)
    if not keys:
        return

    async def operation(client: AsyncRedis) -> None:
        pipeline = client.pipeline()
        for key in keys:
            raw = await client.get(key)
            if raw is None:
                continue
            try:
                value = _json_value(raw)
            except json.JSONDecodeError:
                pipeline.delete(key)
                continue
            if not isinstance(value, dict):
                pipeline.delete(key)
                continue
            value["created_at"] = created_at
            pipeline.set(
                key,
                json.dumps(jsonable_encoder(value), separators=(",", ":")),
                ex=ttl_seconds,
            )
        await pipeline.execute()

    await _run_async(operation)


def delete_matching(namespace: str, predicate: Callable[[dict[str, Any]], bool]) -> None:
    keys_to_delete: list[str] = []
    for key, value in iter_namespace(namespace):
        if predicate(value):
            keys_to_delete.append(key)
    delete_keys(keys_to_delete)


def iter_namespace(namespace: str) -> list[tuple[str, dict[str, Any]]]:
    pattern = f"{_KEY_PREFIX}:{namespace}:*"

    def operation(client: Redis) -> list[tuple[str, dict[str, Any]]]:
        entries: list[tuple[str, dict[str, Any]]] = []
        for key in client.scan_iter(match=pattern, count=100):
            raw = client.get(key)
            if raw is None:
                continue
            try:
                value = _json_value(raw)
            except json.JSONDecodeError:
                client.delete(key)
                continue
            if isinstance(value, dict):
                entries.append((str(key), value))
        return entries

    return _run(operation) or []


def delete_keys(keys: list[str]) -> None:
    if not keys:
        return

    def operation(client: Redis) -> None:
        client.delete(*keys)

    _run(operation)


async def delete_keys_async(keys: list[str]) -> None:
    if not keys:
        return

    async def operation(client: AsyncRedis) -> None:
        await client.delete(*keys)

    await _run_async(operation)


def clear_namespace(namespace: str) -> None:
    pattern = f"{_KEY_PREFIX}:{namespace}:*"
    index_pattern = f"{_KEY_PREFIX}:idx:{namespace}:*"

    def operation(client: Redis) -> None:
        keys = list(client.scan_iter(match=pattern, count=100)) + list(
            client.scan_iter(match=index_pattern, count=100)
        )
        if keys:
            client.delete(*keys)

    _run(operation)


async def clear_namespace_async(namespace: str) -> None:
    pattern = f"{_KEY_PREFIX}:{namespace}:*"
    index_pattern = f"{_KEY_PREFIX}:idx:{namespace}:*"

    async def operation(client: AsyncRedis) -> None:
        keys = [key async for key in client.scan_iter(match=pattern, count=100)] + [
            key async for key in client.scan_iter(match=index_pattern, count=100)
        ]
        if keys:
            await client.delete(*keys)

    await _run_async(operation)


def _run(operation: Callable[[Redis], Any]) -> Any:
    if _running_event_loop():
        if enabled():
            _warn_sync_redis_in_event_loop()
        return None

    client = _get_client()
    if client is None:
        return None
    try:
        return operation(client)
    except (OSError, RedisError):
        _disable_temporarily()
        logger.warning("redis cache operation failed; falling back to local cache", exc_info=True)
        return None


async def _run_async(operation: Callable[[AsyncRedis], Awaitable[Any]]) -> Any:
    client = _get_async_client()
    if client is None:
        return None
    try:
        return await operation(client)
    except (OSError, RedisError):
        _disable_temporarily()
        logger.warning("redis cache operation failed; falling back to local cache", exc_info=True)
        return None


def _get_client() -> Redis | None:
    global _redis_client, _redis_disabled_until, _redis_url

    url = get_settings().redis_url
    if not url:
        return None
    now = monotonic()
    if now < _redis_disabled_until:
        return None
    if _redis_client is not None and _redis_url == url:
        return _redis_client

    _redis_url = url
    _redis_client = Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=_REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
    )
    return _redis_client


def _get_async_client() -> AsyncRedis | None:
    global _async_redis_client, _async_redis_url, _redis_disabled_until

    url = get_settings().redis_url
    if not url:
        return None
    now = monotonic()
    if now < _redis_disabled_until:
        return None
    if _async_redis_client is not None and _async_redis_url == url:
        return _async_redis_client

    _async_redis_url = url
    _async_redis_client = AsyncRedis.from_url(
        url,
        decode_responses=True,
        socket_timeout=_REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
    )
    return _async_redis_client


def _disable_temporarily() -> None:
    global _async_redis_client, _redis_client, _redis_disabled_until
    _async_redis_client = None
    _redis_client = None
    _redis_disabled_until = monotonic() + _REDIS_RETRY_AFTER_SECONDS


def _warn_sync_redis_in_event_loop() -> None:
    global _sync_event_loop_warning_logged

    if _sync_event_loop_warning_logged:
        return
    _sync_event_loop_warning_logged = True
    logger.warning("sync redis cache operation skipped inside event loop; use async cache API")


def _running_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _json_value(raw: object) -> Any:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    elif not isinstance(raw, str):
        raw = str(raw)
    return json.loads(raw)


def _index_keys(namespace: str, resources: frozenset[str], client_id: str | None) -> list[str]:
    keys: list[str] = []
    client_index_value = client_id or "_global"
    for resource in resources:
        keys.append(f"{_KEY_PREFIX}:idx:{namespace}:resource:{resource}")
        keys.append(f"{_KEY_PREFIX}:idx:{namespace}:resource-client:{resource}:{client_index_value}")
    return keys


def _indexed_data_keys(
    namespace: str,
    resources: set[str],
    *,
    client_id: str | None,
) -> set[str]:
    def operation(client: Redis) -> set[str]:
        keys: set[str] = set()
        for resource in resources:
            if client_id is None:
                keys.update(
                    str(key)
                    for key in client.smembers(
                        f"{_KEY_PREFIX}:idx:{namespace}:resource:{resource}"
                    )
                )
                continue
            keys.update(
                str(key)
                for key in client.smembers(
                    f"{_KEY_PREFIX}:idx:{namespace}:resource-client:{resource}:_global"
                )
            )
            keys.update(
                str(key)
                for key in client.smembers(
                    f"{_KEY_PREFIX}:idx:{namespace}:resource-client:{resource}:{client_id}"
                )
            )
        return keys

    return _run(operation) or set()


async def _indexed_data_keys_async(
    namespace: str,
    resources: set[str],
    *,
    client_id: str | None,
) -> set[str]:
    async def operation(client: AsyncRedis) -> set[str]:
        keys: set[str] = set()
        for resource in resources:
            if client_id is None:
                keys.update(
                    str(key)
                    for key in await client.smembers(
                        f"{_KEY_PREFIX}:idx:{namespace}:resource:{resource}"
                    )
                )
                continue
            keys.update(
                str(key)
                for key in await client.smembers(
                    f"{_KEY_PREFIX}:idx:{namespace}:resource-client:{resource}:_global"
                )
            )
            keys.update(
                str(key)
                for key in await client.smembers(
                    f"{_KEY_PREFIX}:idx:{namespace}:resource-client:{resource}:{client_id}"
                )
            )
        return keys

    return await _run_async(operation) or set()
