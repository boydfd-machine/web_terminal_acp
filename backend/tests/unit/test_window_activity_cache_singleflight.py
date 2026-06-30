from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.contexts.activity.api.schemas import ClientWindowsActivityOut
from app.contexts.activity.application import window_activity


class _FakeScalars:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def __iter__(self):
        return iter(self._values)


class _FakeSession:
    def __init__(self, window_ids: list[object]) -> None:
        self._window_ids = window_ids

    async def scalars(self, _query):
        return _FakeScalars(self._window_ids)


@pytest.mark.asyncio
async def test_load_client_windows_activity_singleflights_same_cache_key(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    build_calls = 0
    release_build = asyncio.Event()

    async def build_activity(_session, _client_id, _window_ids, *, include_runtime_tags):
        nonlocal build_calls
        build_calls += 1
        await release_build.wait()
        return ClientWindowsActivityOut()

    monkeypatch.setattr(window_activity, "_redis_activity_cache", lambda _cache_key: None)
    monkeypatch.setattr(window_activity, "_store_redis_activity_cache", lambda *_args: False)
    monkeypatch.setattr(window_activity, "_build_client_windows_activity", build_activity)
    window_activity.clear_client_windows_activity_cache()

    first = asyncio.create_task(
        window_activity.load_client_windows_activity(_FakeSession([window_id]), client_id)
    )
    await asyncio.sleep(0)
    second = asyncio.create_task(
        window_activity.load_client_windows_activity(_FakeSession([window_id]), client_id)
    )
    await asyncio.sleep(0)

    assert build_calls == 1

    release_build.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert first_result == second_result
    assert build_calls == 1
    window_activity.clear_client_windows_activity_cache()
