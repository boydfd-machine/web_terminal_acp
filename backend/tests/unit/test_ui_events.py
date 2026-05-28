import asyncio
import json
from uuid import uuid4

import pytest

from app.services.polling_response_cache import (
    cached_or_stale_json_response,
    cached_json_response,
    clear_polling_response_cache,
    store_json_response,
)
from app.services.ui_events import UiEventHub


@pytest.mark.asyncio
async def test_ui_event_hub_publishes_invalidation_to_subscribers():
    hub = UiEventHub()
    messages: list[str] = []

    async def sender(message: str) -> None:
        messages.append(message)

    client_id = uuid4()
    window_id = uuid4()
    await hub.subscribe(sender)
    await hub.publish_invalidation(
        ["tree", "window", "tree"],
        client_id=client_id,
        window_id=window_id,
        reason="window_updated",
    )

    assert len(messages) == 1
    payload = json.loads(messages[0])
    assert payload["type"] == "invalidate"
    assert payload["seq"] == 1
    assert payload["resources"] == ["tree", "window"]
    assert payload["client_id"] == str(client_id)
    assert payload["window_id"] == str(window_id)
    assert payload["reason"] == "window_updated"


@pytest.mark.asyncio
async def test_ui_event_hub_invalidates_hot_polling_caches(monkeypatch):
    hub = UiEventHub()
    client_id = uuid4()
    cache_key = ("tree", client_id)
    store_json_response(cache_key, {"ok": True}, resources={"tree"}, client_id=client_id)

    cleared_client_ids: list[object] = []

    def fake_clear_client_windows_activity_cache(cleared_client_id=None):
        cleared_client_ids.append(cleared_client_id)

    monkeypatch.setattr(
        "app.services.ui_events.clear_client_windows_activity_cache",
        fake_clear_client_windows_activity_cache,
    )

    await hub.publish_invalidation(["tree"], client_id=client_id, reason="window_updated")

    assert cached_json_response(cache_key) is None
    assert cleared_client_ids == [client_id]
    clear_polling_response_cache()


@pytest.mark.asyncio
async def test_terminal_output_invalidation_leaves_polling_cache_warm(monkeypatch):
    hub = UiEventHub()
    client_id = uuid4()
    cache_key = ("activity", client_id)
    store_json_response(cache_key, {"ok": True}, resources={"window"}, client_id=client_id)

    cleared_client_ids: list[object] = []

    def fake_clear_client_windows_activity_cache(cleared_client_id=None):
        cleared_client_ids.append(cleared_client_id)

    monkeypatch.setattr(
        "app.services.ui_events.clear_client_windows_activity_cache",
        fake_clear_client_windows_activity_cache,
    )

    await hub.publish_invalidation(["window"], client_id=client_id, reason="terminal_output")

    cached = cached_or_stale_json_response(cache_key)
    assert cached is not None and cached.expired
    assert cleared_client_ids == []
    clear_polling_response_cache()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    ["client_seen", "client_hello", "client_heartbeat", "client_inventory_seen"],
)
async def test_client_presence_invalidation_leaves_polling_cache_warm(reason):
    hub = UiEventHub()
    client_id = uuid4()
    cache_key = ("clients", client_id)
    store_json_response(cache_key, {"ok": True}, resources={"clients"}, client_id=client_id)

    await hub.publish_invalidation(["clients"], client_id=client_id, reason=reason)

    cached = cached_or_stale_json_response(cache_key)
    assert cached is not None and cached.expired
    clear_polling_response_cache()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        "agent_work_presence",
        "ai_event",
        "claude_jsonl_ingested",
        "git_worktree",
        "terminal_command",
        "trace_ingested",
    ],
)
async def test_activity_only_invalidations_leave_polling_cache_warm(reason):
    hub = UiEventHub()
    client_id = uuid4()
    cache_key = ("activity", client_id)
    store_json_response(cache_key, {"ok": True}, resources={"window", "tree"}, client_id=client_id)

    await hub.publish_invalidation(["window", "tree"], client_id=client_id, reason=reason)

    cached = cached_or_stale_json_response(cache_key)
    assert cached is not None and cached.expired
    clear_polling_response_cache()


@pytest.mark.asyncio
async def test_ui_event_hub_debounces_invalidations_by_key():
    hub = UiEventHub()
    messages: list[str] = []

    async def sender(message: str) -> None:
        messages.append(message)

    client_id = uuid4()
    await hub.subscribe(sender)
    await hub.publish_debounced_invalidation(
        ("terminal_output", client_id),
        ["window"],
        client_id=client_id,
        reason="terminal_output",
        delay_seconds=0.01,
    )
    await hub.publish_debounced_invalidation(
        ("terminal_output", client_id),
        ["tree", "search"],
        client_id=client_id,
        reason="terminal_output",
        delay_seconds=0.01,
    )
    await asyncio.sleep(0.05)

    assert len(messages) == 1
    payload = json.loads(messages[0])
    assert payload["type"] == "invalidate"
    assert set(payload["resources"]) == {"window", "tree", "search"}
    assert payload["client_id"] == str(client_id)
