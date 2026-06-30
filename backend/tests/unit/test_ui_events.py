import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import WebSocketDisconnect
import pytest

from app.platform.ui_event_bridge import (
    RedisUiEventPublisher,
    _consume_pubsub_messages,
    publish_local_ui_event_message,
)
from app.platform import ui_events_routes
from app.services.polling_response_cache import (
    cached_or_stale_json_response,
    cached_json_response,
    clear_polling_response_cache,
    store_json_response,
)
from app.services.ui_events import UiEventHub


class _DisconnectingInitialSendWebSocket:
    def __init__(self, hub: UiEventHub) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(ui_event_hub=hub))
        self.accepted = False
        self.headers = {}

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True

    async def send_json(self, _payload: dict[str, object]) -> None:
        raise WebSocketDisconnect(code=1006)

    async def send_text(self, _message: str) -> None:
        raise AssertionError("disconnected websocket should not be subscribed")

    async def receive(self) -> dict[str, object]:
        raise AssertionError("disconnected websocket should not enter receive loop")


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
async def test_ui_events_websocket_handles_initial_send_disconnect(monkeypatch):
    hub = UiEventHub()
    websocket = _DisconnectingInitialSendWebSocket(hub)

    async def fake_require_websocket_auth(_websocket) -> bool:
        return True

    monkeypatch.setattr(ui_events_routes, "require_websocket_auth", fake_require_websocket_auth)

    await ui_events_routes.ui_events_websocket(websocket)

    assert websocket.accepted is True
    assert hub._subscribers == set()


@pytest.mark.asyncio
async def test_ui_event_hub_drops_slow_subscribers_without_blocking(monkeypatch):
    monkeypatch.setattr("app.services.ui_events.UI_EVENT_SEND_TIMEOUT_SECONDS", 0.01)
    hub = UiEventHub()
    messages: list[str] = []

    async def slow_sender(_message: str) -> None:
        await asyncio.sleep(1)

    async def fast_sender(message: str) -> None:
        messages.append(message)

    await hub.subscribe(slow_sender)
    await hub.subscribe(fast_sender)
    await asyncio.wait_for(
        hub.publish_invalidation(["tree"], client_id=uuid4(), reason="window_created"),
        timeout=0.1,
    )

    assert len(messages) == 1


@pytest.mark.asyncio
async def test_ui_event_hub_invalidates_hot_polling_caches(monkeypatch):
    hub = UiEventHub()
    client_id = uuid4()
    cache_key = ("tree", client_id)
    store_json_response(cache_key, {"ok": True}, resources={"tree"}, client_id=client_id)

    cleared_client_ids: list[object] = []

    async def fake_clear_client_windows_activity_cache(cleared_client_id=None):
        cleared_client_ids.append(cleared_client_id)

    monkeypatch.setattr(
        "app.services.ui_events.clear_client_windows_activity_cache_async",
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

    async def fake_clear_client_windows_activity_cache(cleared_client_id=None):
        cleared_client_ids.append(cleared_client_id)

    monkeypatch.setattr(
        "app.services.ui_events.clear_client_windows_activity_cache_async",
        fake_clear_client_windows_activity_cache,
    )

    await hub.publish_invalidation(["window"], client_id=client_id, reason="terminal_output")

    cached = cached_or_stale_json_response(cache_key)
    assert cached is not None and cached.expired
    assert cleared_client_ids == []
    clear_polling_response_cache()


@pytest.mark.asyncio
async def test_activity_invalidation_clears_agent_work_status_cache(monkeypatch):
    hub = UiEventHub()
    client_id = uuid4()
    window_id = uuid4()
    cleared: list[tuple[object, object]] = []

    monkeypatch.setattr(
        "app.services.ui_events.clear_agent_work_status_cache",
        lambda cleared_client_id=None, cleared_window_id=None: cleared.append(
            (cleared_client_id, cleared_window_id)
        ),
    )

    await hub.publish_invalidation(
        ["agent_record", "window", "search"],
        client_id=client_id,
        window_id=window_id,
        reason="ai_event",
    )

    assert cleared == [(client_id, window_id)]


@pytest.mark.asyncio
async def test_redis_ui_event_publisher_round_trips_to_local_hub():
    class FakeRedis:
        def __init__(self) -> None:
            self.published: list[tuple[str, str]] = []

        async def publish(self, channel: str, message: str) -> None:
            self.published.append((channel, message))

    redis = FakeRedis()
    publisher = RedisUiEventPublisher(redis, "ui-events")
    hub = UiEventHub()
    messages: list[str] = []
    client_id = uuid4()
    window_id = uuid4()

    async def sender(message: str) -> None:
        messages.append(message)

    await hub.subscribe(sender)
    await publisher.publish_invalidation(
        ["agent_record", "window", "search"],
        client_id=client_id,
        window_id=window_id,
        reason="ai_event",
    )
    channel, redis_message = redis.published[0]
    await publish_local_ui_event_message(hub, redis_message)

    assert channel == "ui-events"
    payload = json.loads(messages[0])
    assert payload["resources"] == ["agent_record", "window", "search"]
    assert payload["client_id"] == str(client_id)
    assert payload["window_id"] == str(window_id)
    assert payload["reason"] == "ai_event"


@pytest.mark.asyncio
async def test_redis_ui_event_bridge_polls_without_idle_disconnects():
    class FakePubSub:
        def __init__(self, redis_message: str) -> None:
            self.messages = [
                {"type": "subscribe", "data": None},
                None,
                {"type": "message", "data": redis_message},
            ]

        async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float):
            assert ignore_subscribe_messages is True
            assert timeout == 1.0
            if self.messages:
                return self.messages.pop(0)
            raise asyncio.CancelledError

    hub = UiEventHub()
    messages: list[str] = []
    client_id = uuid4()
    window_id = uuid4()
    redis_message = json.dumps(
        {
            "type": "invalidate",
            "resources": ["agent_record"],
            "client_id": str(client_id),
            "window_id": str(window_id),
            "reason": "ai_event",
        },
        separators=(",", ":"),
    )

    async def sender(message: str) -> None:
        messages.append(message)

    await hub.subscribe(sender)
    with pytest.raises(asyncio.CancelledError):
        await _consume_pubsub_messages(hub, FakePubSub(redis_message))

    assert len(messages) == 1
    payload = json.loads(messages[0])
    assert payload["resources"] == ["agent_record"]
    assert payload["client_id"] == str(client_id)
    assert payload["window_id"] == str(window_id)


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
