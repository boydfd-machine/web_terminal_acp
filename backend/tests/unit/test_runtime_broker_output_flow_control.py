from tests.unit.test_runtime_broker_support import *

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
    await broker.unsubscribe(client_id, window_id, second_sender)

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
    try:
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
    finally:
        release_slow_sender.set()
        await broker.unsubscribe(client_id, window_id, slow_sender)

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
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_waits_for_output_ack_before_next_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 5)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 5)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, b"first")
    await broker.publish_output(client_id, window_id, b"-second")

    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"first"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"first output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    await asyncio.sleep(0.05)
    assert received == [b"first"]

    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"first", b"-seco"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"second output was not delivered after ack: {received!r}")
        await asyncio.sleep(0.01)

    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"first", b"-seco", b"nd"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"final output was not delivered after ack: {received!r}")
        await asyncio.sleep(0.01)
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_keeps_large_default_output_frame() -> None:
    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    payload = b"x" * (96 * 1024)
    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, payload)

    deadline = asyncio.get_event_loop().time() + 1
    while received != [payload]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"large output was split or not delivered: {[len(chunk) for chunk in received]!r}")
        await asyncio.sleep(0.01)
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_splits_oversized_output_by_ack_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 4)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 4)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, b"abcdefghij")

    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"abcd"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"first output slice was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    await asyncio.sleep(0.05)
    assert received == [b"abcd"]

    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"abcd", b"efgh"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"second output slice was not delivered after ack: {received!r}")
        await asyncio.sleep(0.01)

    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"abcd", b"efgh", b"ij"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"final output slice was not delivered after ack: {received!r}")
        await asyncio.sleep(0.01)
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_allows_multiple_frames_within_ack_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 4)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 12)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, b"aaaabbbbccccdddd")

    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaa", b"bbbb", b"cccc"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"windowed output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    await asyncio.sleep(0.05)
    assert received == [b"aaaa", b"bbbb", b"cccc"]

    await broker.acknowledge_output(client_id, window_id, sender, bytes_acked=4)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaa", b"bbbb", b"cccc", b"dddd"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"output did not continue after byte ack: {received!r}")
        await asyncio.sleep(0.01)
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_bare_ack_releases_one_in_flight_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 4)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 8)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []

    async def sender(data: bytes) -> None:
        received.append(data)

    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, b"aaaabbbbcccc")

    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaa", b"bbbb"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"initial window output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaa", b"bbbb", b"cccc"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"bare ack did not release one frame: {received!r}")
        await asyncio.sleep(0.01)
    await broker.unsubscribe(client_id, window_id, sender)

@pytest.mark.asyncio
async def test_ack_capable_subscriber_coalesces_small_output_within_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 12)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 12)

    client_id = uuid4()
    window_id = uuid4()
    received: list[bytes] = []
    release_sender = asyncio.Event()
    failures: list[BaseException] = []

    async def sender(data: bytes) -> None:
        received.append(data)
        await release_sender.wait()

    async def on_failure(_writer, exc: BaseException) -> None:
        failures.append(exc)

    writer = broker_module._TerminalSubscriberWriter(
        client_id=client_id,
        window_id=window_id,
        output_sender=sender,
        status_sender=None,
        on_failure=on_failure,
    )
    async with writer._condition:
        writer._ack_enabled = True
        for chunk in (b"aaaa", b"bbbb", b"cccc"):
            writer._queue.append(broker_module._QueuedSubscriberMessage(payload=chunk, size=len(chunk)))
            writer._queued_bytes += len(chunk)
        writer._condition.notify_all()

    writer.start()

    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaabbbbcccc"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"small output was not coalesced: {received!r}")
        await asyncio.sleep(0.01)

    release_sender.set()
    await writer.close()
    assert failures == []

@pytest.mark.asyncio
async def test_ack_capable_subscriber_sheds_old_output_when_queue_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_QUEUE_MAX_BYTES", 8)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_QUEUE_MAX_MESSAGES", 2)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_COALESCE_BYTES", 4)
    monkeypatch.setattr(broker_module, "SUBSCRIBER_WRITER_ACK_WINDOW_BYTES", 4)

    client_id = uuid4()
    window_id = uuid4()
    broker = TerminalBroker()
    received: list[bytes] = []
    release_sender = asyncio.Event()

    async def sender(data: bytes) -> None:
        received.append(data)
        await release_sender.wait()

    await broker.subscribe(client_id, window_id, sender)
    await broker.acknowledge_output(client_id, window_id, sender)

    await broker.publish_output(client_id, window_id, b"aaaa")
    deadline = asyncio.get_event_loop().time() + 1
    while received != [b"aaaa"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"first output was not delivered: {received!r}")
        await asyncio.sleep(0.01)

    await broker.publish_output(client_id, window_id, b"bbbb")
    await broker.publish_output(client_id, window_id, b"cccc")
    await broker.publish_output(client_id, window_id, b"dddd")

    assert sender in broker._subscribers.get((client_id, window_id), {})

    release_sender.set()
    await broker.acknowledge_output(client_id, window_id, sender)
    deadline = asyncio.get_event_loop().time() + 1
    while len(received) < 2:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"new output was not delivered after shedding: {received!r}")
        await asyncio.sleep(0.01)

    assert received[-1] == b"dddd"
    await broker.unsubscribe(client_id, window_id, sender)
