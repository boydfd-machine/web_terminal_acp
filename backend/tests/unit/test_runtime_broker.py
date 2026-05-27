import asyncio
from uuid import UUID, uuid4

import pytest

from app.services.runtime import broker as broker_module
from app.services.runtime.broker import TerminalBroker, terminal_status_message
from app.services.runtime.types import RuntimeWindow


class FakeRuntime:
    def __init__(self) -> None:
        self.created: list[tuple[str | None, str | None]] = []
        self.attached: list[RuntimeWindow] = []
        self.detached: list[RuntimeWindow] = []
        self.attached_local_window_ids = []
        self.detached_local_window_ids = []
        self.attached_view_ids = []
        self.detached_view_ids = []
        self.inputs: list[tuple[RuntimeWindow, bytes]] = []
        self.input_view_ids = []
        self.resizes: list[tuple[RuntimeWindow, int, int]] = []
        self.resize_view_ids = []
        self.selections: list[tuple[RuntimeWindow, RuntimeWindow]] = []
        self.selection_view_ids = []
        self.detach_started = asyncio.Event()
        self.allow_detach: asyncio.Event | None = None
        self.attach_result: RuntimeWindow | None = None
        self.selection_result: RuntimeWindow | None = None

    async def create_window(
        self, cwd: str | None = None, shell_command: str | None = None
    ) -> RuntimeWindow:
        self.created.append((cwd, shell_command))
        return RuntimeWindow(session_id="session", window_id="@1")

    async def attach(
        self,
        window: RuntimeWindow,
        sender,
        *,
        local_window_id=None,
        selection_callback=None,
        view_id=None,
    ) -> None:
        self.attached.append(window)
        self.attached_local_window_ids.append(local_window_id)
        self.attached_view_ids.append(view_id)
        await sender(b"attached")
        return self.attach_result or window

    async def detach(self, window: RuntimeWindow, *, local_window_id=None, view_id=None) -> None:
        self.detach_started.set()
        self.detached_local_window_ids.append(local_window_id)
        self.detached_view_ids.append(view_id)
        if self.allow_detach is not None:
            await self.allow_detach.wait()
        self.detached.append(window)

    async def send_input(
        self, window: RuntimeWindow, data: bytes, *, local_window_id=None, view_id=None
    ) -> None:
        self.inputs.append((window, data))
        self.input_view_ids.append(view_id)

    async def resize(self, window: RuntimeWindow, *, cols: int, rows: int, local_window_id=None, view_id=None) -> None:
        self.resizes.append((window, cols, rows))
        self.resize_view_ids.append(view_id)

    async def select_window(
        self,
        current_window: RuntimeWindow,
        next_window: RuntimeWindow,
        *,
        local_window_id,
        view_id=None,
    ) -> None:
        self.selections.append((current_window, next_window))
        self.selection_view_ids.append(view_id)
        return self.selection_result or next_window


@pytest.mark.asyncio
async def test_publish_output_fans_out_without_holding_subscription_lock() -> None:
    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[tuple[str, bytes]] = []

    async def unsubscribing_sender(data: bytes) -> None:
        received.append(("first", data))
        await broker.unsubscribe(client_id, window_id, unsubscribing_sender)

    async def second_sender(data: bytes) -> None:
        received.append(("second", data))

    await broker.subscribe(client_id, window_id, unsubscribing_sender)
    await broker.subscribe(client_id, window_id, second_sender)

    await asyncio.wait_for(broker.publish_output(client_id, window_id, b"chunk"), timeout=1)
    deadline = asyncio.get_event_loop().time() + 1
    while len(received) < 2:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"subscriber output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    assert sorted(received) == [("first", b"chunk"), ("second", b"chunk")]


@pytest.mark.asyncio
async def test_publish_output_returns_after_enqueue_when_browser_sender_is_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote terminal output handling must not wait on a slow browser socket.

    A WAN browser can make websocket.send_bytes take hundreds of milliseconds
    or seconds. The broker should accept terminal output into a per-subscriber
    writer queue quickly; otherwise the bulk terminal-output worker stalls and
    tmux output/echo feels slow even though the underlying tmux session is
    responsive.
    """

    monkeypatch.setattr(
        broker_module,
        "PUBLISH_OUTPUT_SUBSCRIBER_TIMEOUT_SECONDS",
        0.2,
    )

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    release_slow_sender = asyncio.Event()
    slow_sender_started = asyncio.Event()
    sent: list[bytes] = []

    async def slow_sender(data: bytes) -> None:
        sent.append(data)
        slow_sender_started.set()
        await release_slow_sender.wait()

    await broker.subscribe(client_id, window_id, slow_sender)

    started = asyncio.get_event_loop().time()
    await asyncio.wait_for(
        broker.publish_output(client_id, window_id, b"first"),
        timeout=0.05,
    )
    elapsed = asyncio.get_event_loop().time() - started

    await asyncio.wait_for(slow_sender_started.wait(), timeout=0.1)
    release_slow_sender.set()

    assert sent == [b"first"]
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_publish_output_drops_slow_subscriber_when_queue_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_QUEUE_MAX_BYTES", 8)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_QUEUE_MAX_MESSAGES", 2)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 4)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    sender_started = asyncio.Event()
    release_sender = asyncio.Event()
    sent: list[bytes] = []

    async def slow_sender(data: bytes) -> None:
        sent.append(data)
        sender_started.set()
        await release_sender.wait()

    await broker.subscribe(client_id, window_id, slow_sender)
    await broker.publish_output(client_id, window_id, b"aaaa")
    await asyncio.wait_for(sender_started.wait(), timeout=1)

    await broker.publish_output(client_id, window_id, b"bbbb")
    await broker.publish_output(client_id, window_id, b"cccc")
    await broker.publish_output(client_id, window_id, b"dddd")

    release_sender.set()
    deadline = asyncio.get_event_loop().time() + 1
    while slow_sender in broker._subscribers.get((client_id, window_id), {}):
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("slow subscriber was not dropped after queue saturation")
        await asyncio.sleep(0.01)

    assert sent == [b"aaaa"]


@pytest.mark.asyncio
async def test_publish_output_coalesces_small_chunks_without_losing_bytes() -> None:
    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, sender)
    await broker.publish_output(client_id, window_id, b"ab")
    await broker.publish_output(client_id, window_id, b"cd")
    await broker.publish_output(client_id, window_id, b"ef")

    deadline = asyncio.get_event_loop().time() + 1
    while b"".join(received) != b"abcdef":
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"coalesced output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    assert b"".join(received) == b"abcdef"


@pytest.mark.asyncio
async def test_publish_output_drops_slow_subscriber_and_keeps_healthy_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subscriber whose send blocks past the configured timeout must be
    dropped and unsubscribed without delaying the broker beyond the timeout,
    so a half-open browser WebSocket cannot stall the bulk-WS worker."""

    monkeypatch.setattr(
        broker_module,
        "PUBLISH_OUTPUT_SUBSCRIBER_TIMEOUT_SECONDS",
        0.05,
    )

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    healthy_received: list[bytes] = []
    slow_calls = 0
    release_slow = asyncio.Event()

    async def slow_sender(data: bytes) -> None:
        nonlocal slow_calls
        slow_calls += 1
        await release_slow.wait()

    async def healthy_sender(data: bytes) -> None:
        healthy_received.append(data)

    await broker.subscribe(client_id, window_id, slow_sender)
    await broker.subscribe(client_id, window_id, healthy_sender)

    started = asyncio.get_event_loop().time()
    await asyncio.wait_for(
        broker.publish_output(client_id, window_id, b"first"),
        timeout=1.0,
    )
    elapsed_first = asyncio.get_event_loop().time() - started

    await broker.publish_output(client_id, window_id, b"second")

    await asyncio.wait_for(asyncio.to_thread(lambda: None), timeout=1)
    deadline = asyncio.get_event_loop().time() + 1
    while slow_calls == 0 or b"".join(healthy_received) != b"firstsecond":
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"subscriber output was not delivered: slow={slow_calls}, healthy={healthy_received!r}"
            )
        await asyncio.sleep(0.01)
    release_slow.set()

    assert slow_calls == 1
    assert b"".join(healthy_received) == b"firstsecond"
    assert elapsed_first < 0.5, (
        "publish_output must not wait substantially longer than the "
        "per-subscriber timeout when one subscriber is stuck"
    )


@pytest.mark.asyncio
async def test_publish_output_removes_failing_subscribers_and_continues() -> None:
    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    failures: list[bytes] = []
    received: list[bytes] = []

    async def failing_sender(data: bytes) -> None:
        failures.append(data)
        raise RuntimeError("stale browser websocket")

    async def healthy_sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, failing_sender)
    await broker.subscribe(client_id, window_id, healthy_sender)

    await broker.publish_output(client_id, window_id, b"first")
    deadline = asyncio.get_event_loop().time() + 1
    while failures != [b"first"] or healthy_sender not in broker._subscribers.get((client_id, window_id), {}):
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"failing sender was not processed: failures={failures!r}, received={received!r}"
            )
        await asyncio.sleep(0.01)
    await broker.publish_output(client_id, window_id, b"second")
    deadline = asyncio.get_event_loop().time() + 1
    while b"".join(received) != b"firstsecond":
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"healthy sender did not receive both chunks: {received!r}")
        await asyncio.sleep(0.01)

    assert failures == [b"first"]
    assert b"".join(received) == b"firstsecond"


@pytest.mark.asyncio
async def test_broker_forwards_input_and_resize_to_registered_runtime() -> None:
    client_id = uuid4()
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@2")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    await broker.send_input(client_id, browser_window_id, runtime_window, b"ls -la\n")
    await broker.resize(client_id, browser_window_id, runtime_window, cols=120, rows=40)

    assert runtime.inputs == [(runtime_window, b"ls -la\n")]
    assert runtime.resizes == [(runtime_window, 120, 40)]


@pytest.mark.asyncio
async def test_broker_attach_uses_runtime_and_publishes_initial_output() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@3")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, browser_window_id, sender)
    await broker.attach(client_id, browser_window_id, runtime_window)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"attached"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"attach output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    assert runtime.attached == [runtime_window]
    assert received == [b"attached"]


@pytest.mark.asyncio
async def test_broker_attach_returns_recreated_runtime_window() -> None:
    client_id = uuid4()
    browser_window_id = uuid4()
    requested_runtime_window = RuntimeWindow(session_id="session", window_id="@3")
    recreated_runtime_window = RuntimeWindow(session_id="session", window_id="@9")
    runtime = FakeRuntime()
    runtime.attach_result = recreated_runtime_window
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    actual = await broker.attach(client_id, browser_window_id, requested_runtime_window)

    assert actual == recreated_runtime_window
    assert runtime.attached == [requested_runtime_window]
    assert broker._attachments[(client_id, browser_window_id)] == recreated_runtime_window


@pytest.mark.asyncio
async def test_broker_view_id_scopes_attachment_and_switching() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    first_window_id = uuid4()
    second_window_id = uuid4()
    view_id = uuid4()
    first_runtime_window = RuntimeWindow(session_id="session", window_id="@3")
    second_runtime_window = RuntimeWindow(session_id="session", window_id="@4")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    async def sender(_data: bytes) -> None:
        return None

    await broker.subscribe(client_id, view_id, sender)
    await broker.attach(client_id, first_window_id, first_runtime_window, view_id=view_id)
    await broker.send_input(client_id, first_window_id, first_runtime_window, b"one", view_id=view_id)
    await broker.select_window(
        client_id,
        view_id,
        first_window_id,
        first_runtime_window,
        second_window_id,
        second_runtime_window,
    )
    await broker.send_input(client_id, second_window_id, second_runtime_window, b"two", view_id=view_id)
    await broker.unsubscribe(client_id, view_id, sender)

    assert runtime.attached_local_window_ids == [first_window_id]
    assert runtime.attached_view_ids == [view_id]
    assert runtime.inputs == [(first_runtime_window, b"one"), (second_runtime_window, b"two")]
    assert runtime.input_view_ids == [view_id, view_id]
    assert runtime.selections == [(first_runtime_window, second_runtime_window)]
    assert runtime.selection_view_ids == [view_id]
    assert runtime.detached == [second_runtime_window]
    assert runtime.detached_local_window_ids == [second_window_id]
    assert runtime.detached_view_ids == [view_id]


@pytest.mark.asyncio
async def test_broker_detaches_runtime_after_last_subscriber_unsubscribes() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@4")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    async def first_sender(data: bytes) -> None:
        return None

    async def second_sender(data: bytes) -> None:
        return None

    await broker.subscribe(client_id, browser_window_id, first_sender)
    await broker.subscribe(client_id, browser_window_id, second_sender)
    await broker.attach(client_id, browser_window_id, runtime_window)

    await broker.unsubscribe(client_id, browser_window_id, first_sender)

    assert runtime.detached == []

    await broker.unsubscribe(client_id, browser_window_id, second_sender)

    assert runtime.detached == [runtime_window]


@pytest.mark.asyncio
async def test_broker_publishes_status_to_status_subscribers() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    broker = TerminalBroker()
    received_statuses: list[str] = []

    async def output_sender(data: bytes) -> None:
        raise AssertionError("status publish must not use output sender")

    async def status_sender(message: str) -> None:
        received_statuses.append(message)

    await broker.subscribe(client_id, browser_window_id, output_sender, status_sender)
    await broker.publish_status(
        client_id,
        browser_window_id,
        terminal_status_message("unavailable", reason="client_offline"),
    )
    deadline = asyncio.get_event_loop().time() + 1
    while not received_statuses:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("status was not delivered")
        await asyncio.sleep(0.01)

    assert received_statuses == [
        '{"type":"terminal_status","status":"unavailable","reason":"client_offline"}'
    ]


@pytest.mark.asyncio
async def test_broker_clear_client_removes_attachments_and_publishes_status() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@4")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)
    received_statuses: list[str] = []

    async def output_sender(data: bytes) -> None:
        return None

    async def status_sender(message: str) -> None:
        received_statuses.append(message)

    await broker.subscribe(client_id, browser_window_id, output_sender, status_sender)
    await broker.attach(client_id, browser_window_id, runtime_window)

    await broker.clear_client(
        client_id,
        status_message=terminal_status_message("unavailable", reason="client_offline"),
    )
    await broker.attach(client_id, browser_window_id, runtime_window)
    deadline = asyncio.get_event_loop().time() + 1
    while not received_statuses:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("status was not delivered")
        await asyncio.sleep(0.01)

    assert runtime.attached == [runtime_window, runtime_window]
    assert runtime.detached == []
    assert received_statuses == [
        '{"type":"terminal_status","status":"unavailable","reason":"client_offline"}'
    ]


@pytest.mark.asyncio
async def test_publish_output_is_not_blocked_by_pending_detach() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@5")
    runtime = FakeRuntime()
    runtime.allow_detach = asyncio.Event()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    async def sender(data: bytes) -> None:
        return None

    await broker.subscribe(client_id, browser_window_id, sender)
    await broker.attach(client_id, browser_window_id, runtime_window)

    unsubscribe_task = asyncio.create_task(
        broker.unsubscribe(client_id, browser_window_id, sender)
    )
    await runtime.detach_started.wait()

    await asyncio.wait_for(broker.publish_output(client_id, browser_window_id, b"late output"), timeout=0.1)

    runtime.allow_detach.set()
    await unsubscribe_task


@pytest.mark.asyncio
async def test_reconnect_waits_for_pending_final_detach_before_reattaching() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@5")
    runtime = FakeRuntime()
    runtime.allow_detach = asyncio.Event()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    async def first_sender(data: bytes) -> None:
        return None

    async def reconnect_sender(data: bytes) -> None:
        return None

    await broker.subscribe(client_id, browser_window_id, first_sender)
    await broker.attach(client_id, browser_window_id, runtime_window)

    unsubscribe_task = asyncio.create_task(
        broker.unsubscribe(client_id, browser_window_id, first_sender)
    )
    await runtime.detach_started.wait()

    subscribe_completed = asyncio.Event()
    attach_completed = asyncio.Event()

    async def reconnect() -> None:
        await broker.subscribe(client_id, browser_window_id, reconnect_sender)
        subscribe_completed.set()
        await broker.attach(client_id, browser_window_id, runtime_window)
        attach_completed.set()

    reconnect_task = asyncio.create_task(reconnect())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    subscribe_completed_while_detaching = subscribe_completed.is_set()
    attach_completed_while_detaching = attach_completed.is_set()

    runtime.allow_detach.set()
    await unsubscribe_task
    await reconnect_task

    assert subscribe_completed_while_detaching
    assert not attach_completed_while_detaching
    assert runtime.detached == [runtime_window]
    assert runtime.attached == [runtime_window, runtime_window]
