from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import cache_backend
from app.services import polling_response_cache
from app.services.polling_response_cache import (
    begin_response_cache_build,
    cached_json_response,
    clear_polling_response_cache,
    expire_polling_response_cache,
    finish_response_cache_build,
    invalidate_polling_response_cache,
    store_json_response,
)


def test_polling_response_cache_uses_redis_when_available(monkeypatch) -> None:
    stored: dict[str, dict[str, object]] = {}

    monkeypatch.setattr(
        cache_backend,
        "set_indexed_json",
        lambda namespace, key, value, *, resources, client_id, ttl_seconds: stored.setdefault(repr(key), value) is value,
    )
    monkeypatch.setattr(cache_backend, "get_json", lambda namespace, key: stored.get(repr(key)))
    monkeypatch.setattr(cache_backend, "delete_keys", lambda keys: None)
    monkeypatch.setattr(cache_backend, "clear_namespace", lambda namespace: stored.clear())
    monkeypatch.setattr(cache_backend, "delete_indexed", lambda namespace, resources, *, client_id: None)
    monkeypatch.setattr(cache_backend, "expire_indexed_json", lambda namespace, resources, *, client_id, created_at, ttl_seconds: None)

    cache_key = ("tree", uuid4())
    response = store_json_response(cache_key, {"ok": True}, resources={"tree"})

    assert response.status_code == 200
    assert cached_json_response(cache_key) is not None

    clear_polling_response_cache()


def test_polling_response_cache_invalidates_redis_entries(monkeypatch) -> None:
    client_id = uuid4()
    delete_calls: list[tuple[str, set[str], str | None]] = []

    monkeypatch.setattr(cache_backend, "delete_indexed", lambda namespace, resources, *, client_id: delete_calls.append((namespace, resources, client_id)))
    monkeypatch.setattr(cache_backend, "clear_namespace", lambda namespace: None)

    invalidate_polling_response_cache({"tree"}, client_id=client_id)

    assert delete_calls == [("polling-response", {"tree"}, str(client_id))]


def test_polling_response_cache_expires_redis_entries(monkeypatch) -> None:
    client_id = uuid4()
    expire_calls: list[tuple[str, set[str], str | None, float, int]] = []

    monkeypatch.setattr(
        cache_backend,
        "expire_indexed_json",
        lambda namespace, resources, *, client_id, created_at, ttl_seconds: expire_calls.append(
            (namespace, resources, client_id, created_at, ttl_seconds)
        ),
    )
    monkeypatch.setattr(cache_backend, "clear_namespace", lambda namespace: None)
    monkeypatch.setattr(polling_response_cache, "monotonic", lambda: 100.0)

    expire_polling_response_cache({"window"}, client_id=client_id)

    assert expire_calls == [("polling-response", {"window"}, str(client_id), 89.0, 60)]


@pytest.mark.asyncio
async def test_cache_backend_skips_sync_redis_inside_event_loop(monkeypatch) -> None:
    def fail_get_client():
        raise AssertionError("sync Redis client should not be opened inside the event loop")

    monkeypatch.setattr(cache_backend, "_get_client", fail_get_client)

    assert cache_backend.get_json("polling-response", ("tree", uuid4())) is None


@pytest.mark.asyncio
async def test_cache_backend_uses_async_redis_inside_event_loop(monkeypatch) -> None:
    cache_key_parts = ("tree", uuid4())
    expected_key = cache_backend.cache_key("polling-response", cache_key_parts)
    requested_keys: list[str] = []

    class FakeAsyncRedis:
        async def get(self, key: str) -> str:
            requested_keys.append(key)
            return '{"ok":true}'

    monkeypatch.setattr(cache_backend, "_get_async_client", lambda: FakeAsyncRedis())

    assert await cache_backend.get_json_async("polling-response", cache_key_parts) == {"ok": True}
    assert requested_keys == [expected_key]


@pytest.mark.asyncio
async def test_cache_backend_set_indexed_json_async_writes_indexes(monkeypatch) -> None:
    cache_key_parts = ("tree", uuid4())
    data_key = cache_backend.cache_key("polling-response", cache_key_parts)
    calls: list[tuple[object, ...]] = []

    class FakePipeline:
        def set(self, key: str, payload: str, *, ex: int):
            calls.append(("set", key, payload, ex))
            return self

        def sadd(self, key: str, member: str):
            calls.append(("sadd", key, member))
            return self

        def expire(self, key: str, ttl_seconds: int):
            calls.append(("expire", key, ttl_seconds))
            return self

        async def execute(self):
            calls.append(("execute",))

    class FakeAsyncRedis:
        def pipeline(self) -> FakePipeline:
            return FakePipeline()

    monkeypatch.setattr(cache_backend, "_get_async_client", lambda: FakeAsyncRedis())

    assert await cache_backend.set_indexed_json_async(
        "polling-response",
        cache_key_parts,
        {"ok": True},
        resources=frozenset({"tree"}),
        client_id="client-1",
        ttl_seconds=60,
    )
    assert calls == [
        ("set", data_key, '{"ok":true}', 60),
        ("sadd", "web-terminal-acp:cache:idx:polling-response:resource:tree", data_key),
        ("expire", "web-terminal-acp:cache:idx:polling-response:resource:tree", 60),
        (
            "sadd",
            "web-terminal-acp:cache:idx:polling-response:resource-client:tree:client-1",
            data_key,
        ),
        (
            "expire",
            "web-terminal-acp:cache:idx:polling-response:resource-client:tree:client-1",
            60,
        ),
        ("execute",),
    ]


@pytest.mark.asyncio
async def test_polling_response_cache_async_uses_redis_without_local_fallback(monkeypatch) -> None:
    stored: dict[str, dict[str, object]] = {}

    async def set_indexed_json_async(namespace, key, value, *, resources, client_id, ttl_seconds):
        stored[repr(key)] = value
        return True

    async def get_json_async(namespace, key):
        return stored.get(repr(key))

    monkeypatch.setattr(cache_backend, "set_indexed_json_async", set_indexed_json_async)
    monkeypatch.setattr(cache_backend, "get_json_async", get_json_async)
    monkeypatch.setattr(cache_backend, "delete_keys_async", lambda keys: None)
    monkeypatch.setattr(cache_backend, "clear_namespace", lambda namespace: stored.clear())

    cache_key = ("tree", uuid4())
    response = await polling_response_cache.store_json_response_async(
        cache_key,
        {"ok": True},
        resources={"tree"},
    )

    assert response.status_code == 200
    assert cache_key not in polling_response_cache._response_cache
    assert await polling_response_cache.cached_json_response_async(cache_key) is not None

    clear_polling_response_cache()


@pytest.mark.asyncio
async def test_polling_response_cache_invalidates_redis_entries_async(monkeypatch) -> None:
    client_id = uuid4()
    delete_calls: list[tuple[str, set[str], str | None]] = []

    async def delete_indexed_async(namespace, resources, *, client_id):
        delete_calls.append((namespace, resources, client_id))

    monkeypatch.setattr(cache_backend, "delete_indexed_async", delete_indexed_async)

    await polling_response_cache.invalidate_polling_response_cache_async(
        {"tree"},
        client_id=client_id,
    )

    assert delete_calls == [("polling-response", {"tree"}, str(client_id))]


@pytest.mark.asyncio
async def test_polling_response_cache_singleflight_waits_for_active_build() -> None:
    cache_key = ("tree", uuid4())

    assert begin_response_cache_build(cache_key) is None
    active_build = begin_response_cache_build(cache_key)

    assert active_build is not None
    assert not active_build.done()

    finish_response_cache_build(cache_key)
    await active_build

    assert begin_response_cache_build(cache_key) is None
    finish_response_cache_build(cache_key)
    clear_polling_response_cache()
