from tests.unit.test_runtime_broker_support import *

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
    try:
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
    finally:
        release_slow.set()
        await _unsubscribe_remaining_output_senders(broker, client_id, window_id)

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
    await _unsubscribe_remaining_output_senders(broker, client_id, window_id)

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
async def test_broker_forwards_direct_input_to_base_runtime_window() -> None:
    client_id = uuid4()
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@3")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    await broker.send_input_direct(client_id, browser_window_id, runtime_window, b"prompt\n")

    assert runtime.direct_inputs == [(runtime_window, b"prompt\n")]
    assert runtime.direct_input_local_window_ids == [browser_window_id]

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
    await broker.unsubscribe(client_id, browser_window_id, sender)

@pytest.mark.asyncio
async def test_broker_captures_base_runtime_window_output() -> None:
    client_id = uuid4()
    browser_window_id = uuid4()
    view_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@3")
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    output = await broker.capture_output_bytes(client_id, browser_window_id, runtime_window)

    assert output == b"screen"
    assert runtime.captures == [runtime_window]
    assert runtime.capture_local_window_ids == [browser_window_id]
    assert runtime.capture_view_ids == [None]
    assert runtime.capture_history_lines == [None]

    output = await broker.capture_output_bytes(
        client_id,
        browser_window_id,
        runtime_window,
        view_id=view_id,
        history_lines=5000,
    )

    assert output == b"screen"
    assert runtime.capture_view_ids == [None, view_id]
    assert runtime.capture_history_lines == [None, 5000]

@pytest.mark.asyncio
async def test_broker_reads_runtime_file() -> None:
    client_id = uuid4()
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    output = await broker.read_file_bytes(client_id, "/tmp/artifact.json", max_bytes=1024)

    assert output == b"file"
    assert runtime.file_reads == [("/tmp/artifact.json", 1024)]

@pytest.mark.asyncio
async def test_broker_lists_and_writes_runtime_files() -> None:
    client_id = uuid4()
    runtime = FakeRuntime()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    entries = await broker.list_file_entries(client_id, "/tmp")
    await broker.write_file_bytes(client_id, "/tmp/upload.txt", b"uploaded", overwrite=False)

    assert entries[0].name == "README.md"
    assert runtime.file_lists == ["/tmp"]
    assert runtime.file_writes == [("/tmp/upload.txt", b"uploaded", False)]

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
async def test_broker_passes_missing_window_recreate_permission_to_runtime() -> None:
    client_id = uuid4()
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
    await broker.attach(
        client_id,
        first_window_id,
        first_runtime_window,
        view_id=view_id,
        allow_missing_window_recreate=True,
    )
    await broker.select_window(
        client_id,
        view_id,
        first_window_id,
        first_runtime_window,
        second_window_id,
        second_runtime_window,
        allow_missing_window_recreate=True,
    )

    assert runtime.attach_recreate_permissions == [True]
    assert runtime.selection_recreate_permissions == [True]


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
    await broker.unsubscribe(client_id, browser_window_id, output_sender, status_sender)

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
    await broker.unsubscribe(client_id, browser_window_id, output_sender, status_sender)

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
