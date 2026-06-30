from tests.integration.test_client_agent_ws_support import *
from app.contexts.activity.application.agent_event_queue import AgentEventQueueConfig

def test_bulk_terminal_output_display_worker_keeps_publishing_while_recording_is_backlogged(
    client_agent_db, monkeypatch
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    recording_started = threading.Event()
    release_recording = threading.Event()

    async def slow_record_terminal_output_chunk(*args, **kwargs):
        recording_started.set()
        await asyncio.to_thread(release_recording.wait)
        return None

    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(
        client_agent_router,
        "record_terminal_output_chunk",
        slow_record_terminal_output_chunk,
    )

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            try:
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(window.id, b"first\n").model_dump(),
                        )
                    )
                )
                wait_for_condition(recording_started.is_set)
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(window.id, b"second\n").model_dump(),
                        )
                    )
                )
                wait_for_condition(
                    lambda: broker.published
                    == [
                        (client_agent_db.client_id, window.id, b"first\n"),
                        (client_agent_db.client_id, window.id, b"second\n"),
                    ]
                )
                assert not release_recording.is_set()
            finally:
                release_recording.set()
    finally:
        test_client.close()

def test_bulk_terminal_output_keeps_publishing_when_recording_queue_is_full(
    client_agent_db, monkeypatch
):
    monkeypatch.setattr(client_agent_router, "BACKGROUND_MESSAGE_QUEUE_MAX_SIZE", 1)
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    recording_started = threading.Event()
    release_recording = threading.Event()

    async def slow_record_terminal_output_chunk(*args, **kwargs):
        recording_started.set()
        await asyncio.to_thread(release_recording.wait)
        return None

    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(
        client_agent_router,
        "record_terminal_output_chunk",
        slow_record_terminal_output_chunk,
    )

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            try:
                for text in (b"first\n", b"second\n", b"third\n"):
                    websocket.send_text(
                        encode_agent_message(
                            AgentMessage(
                                type="terminal_output",
                                client_id=client_agent_db.client_id,
                                window_id=window.id,
                                payload=TerminalPayload.from_bytes(window.id, text).model_dump(),
                            )
                        )
                    )
                wait_for_condition(recording_started.is_set)
                wait_for_condition(lambda: len(broker.published) == 3)

                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(window.id, b"fourth\n").model_dump(),
                        )
                    )
                )

                wait_for_condition(
                    lambda: broker.published
                    == [
                        (client_agent_db.client_id, window.id, b"first\n"),
                        (client_agent_db.client_id, window.id, b"second\n"),
                        (client_agent_db.client_id, window.id, b"third\n"),
                        (client_agent_db.client_id, window.id, b"fourth\n"),
                    ]
                )
                assert not release_recording.is_set()
            finally:
                release_recording.set()
    finally:
        test_client.close()

def test_bulk_terminal_output_keeps_publishing_when_ai_event_queue_is_full(
    client_agent_db, monkeypatch
):
    monkeypatch.setattr(client_agent_router, "BACKGROUND_MESSAGE_QUEUE_MAX_SIZE", 1)
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    ai_event_started = threading.Event()
    release_ai_event = threading.Event()

    async def slow_handle_ai_event(*args, **kwargs):
        ai_event_started.set()
        await asyncio.to_thread(release_ai_event.wait)

    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(
        client_agent_router,
        "_handle_ai_event_message_with_ack_sender",
        slow_handle_ai_event,
    )

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            try:
                for index in range(3):
                    websocket.send_text(
                        encode_agent_message(
                            AgentMessage(
                                type="ai_event",
                                client_id=client_agent_db.client_id,
                                window_id=window.id,
                                payload={"payload": {"id": f"queued-{index}"}},
                            )
                        )
                    )
                wait_for_condition(ai_event_started.is_set)

                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(
                                window.id,
                                b"terminal-still-visible\n",
                            ).model_dump(),
                        )
                    )
                )

                wait_for_condition(
                    lambda: broker.published
                    == [
                        (
                            client_agent_db.client_id,
                            window.id,
                            b"terminal-still-visible\n",
                        )
                    ]
                )
                assert not release_ai_event.is_set()
            finally:
                release_ai_event.set()
    finally:
        test_client.close()

def test_bulk_terminal_output_keeps_publishing_when_redis_ai_event_enqueue_blocks(
    client_agent_db, monkeypatch
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    enqueue_started = threading.Event()
    release_enqueue = threading.Event()

    async def slow_enqueue(*args, **kwargs):  # noqa: ANN002, ANN003
        enqueue_started.set()
        await asyncio.to_thread(release_enqueue.wait)
        return "1-0"

    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", slow_enqueue)

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            try:
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="ai_event",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload={
                                "provider": "codex",
                                "payload": {
                                    "trace_id": "blocked-1",
                                    "client_id": str(client_agent_db.client_id),
                                    "virtual_window_id": str(window.id),
                                },
                            },
                        )
                    )
                )
                wait_for_condition(enqueue_started.is_set)

                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(
                                window.id,
                                b"terminal-before-redis-ack\n",
                            ).model_dump(),
                        )
                    )
                )

                wait_for_condition(
                    lambda: broker.published
                    == [
                        (
                            client_agent_db.client_id,
                            window.id,
                            b"terminal-before-redis-ack\n",
                        )
                    ],
                    timeout=0.4,
                )
                assert not release_enqueue.is_set()
            finally:
                release_enqueue.set()
    finally:
        release_enqueue.set()
        test_client.close()

def test_bulk_terminal_output_publishes_before_recording_completes(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    recording_started = threading.Event()
    release_recording = threading.Event()

    async def slow_record_terminal_output_chunk(*args, **kwargs):
        recording_started.set()
        await asyncio.to_thread(release_recording.wait)
        return None

    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(
        client_agent_router,
        "record_terminal_output_chunk",
        slow_record_terminal_output_chunk,
    )

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            try:
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(window.id, b"visible first\n").model_dump(),
                        )
                    )
                )
                wait_for_condition(
                    lambda: broker.published == [(client_agent_db.client_id, window.id, b"visible first\n")]
                )
                wait_for_condition(recording_started.is_set)
                assert broker.published == [(client_agent_db.client_id, window.id, b"visible first\n")]
                assert not release_recording.is_set()
            finally:
                release_recording.set()
    finally:
        test_client.close()

def test_client_agent_bulk_websocket_records_marker_only_terminal_command(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=TerminalPayload.from_bytes(
                            window.id,
                            command_marker(window.id, "echo marker-only"),
                        ).model_dump(),
                    )
                )
            )
            wait_for_condition(lambda: asyncio.run(_event_count(client_agent_db.session_factory)) == 1)
    finally:
        test_client.close()

    async def load_events():
        async with client_agent_db.session_factory() as session:
            return (await session.execute(select(Event))).scalars().all()

    rows = asyncio.run(load_events())
    assert broker.published == []
    assert len(rows) == 1
    assert rows[0].kind == "terminal_input_command"
    assert rows[0].virtual_window_id == window.id
    assert rows[0].payload_json["command"] == "echo marker-only"

def test_client_agent_websocket_records_and_publishes_terminal_output(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    es_client = FakeElasticsearch()
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(app.state, "es_client", es_client, raising=False)
    monkeypatch.setattr(app.state, "es_indexes_ready", True, raising=False)

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=TerminalPayload.from_bytes(window.id, b"remote output\n").model_dump(),
                    )
                )
            )
            wait_for_condition(
                lambda: len(broker.published) == 1
                and len(es_client.indexed_documents) == 1
            )
    finally:
        test_client.close()

    async def load_terminal_state():
        async with client_agent_db.session_factory() as session:
            rows = (await session.execute(select(Event))).scalars().all()
            db_window = await session.get(VirtualWindow, window.id)
            return rows, db_window

    rows, db_window = asyncio.run(load_terminal_state())
    assert broker.published == [(client_agent_db.client_id, window.id, b"remote output\n")]
    assert rows == []
    assert db_window is not None
    assert db_window.terminal_last_output_at is not None
    assert es_client.indexed_documents[0]["document"] == {
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
        "text": "remote output\n",
        "source_event_ids": [],
    }

def test_client_agent_websocket_publishes_terminal_snapshot_without_recording(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = FakeTerminalBroker()
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    payload = TerminalPayload.from_bytes(window.id, b"remote prompt$ ").model_dump()
    payload["is_snapshot"] = True

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=payload,
                    )
                )
            )
            wait_for_condition(lambda: len(broker.published) == 1)
    finally:
        test_client.close()

    async def load_terminal_events():
        async with client_agent_db.session_factory() as session:
            return (await session.execute(select(Event))).scalars().all()

    rows = asyncio.run(load_terminal_events())
    assert broker.published == [(client_agent_db.client_id, window.id, b"remote prompt$ ")]
    assert rows == []

def test_client_agent_websocket_records_terminal_output_when_browser_subscriber_fails(
    client_agent_db, monkeypatch
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = TerminalBroker()
    es_client = FakeElasticsearch()
    failures: list[bytes] = []

    async def failing_sender(data: bytes) -> None:
        failures.append(data)
        raise RuntimeError("stale browser websocket")

    asyncio.run(broker.subscribe(client_agent_db.client_id, window.id, failing_sender))
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)
    monkeypatch.setattr(app.state, "es_client", es_client, raising=False)
    monkeypatch.setattr(app.state, "es_indexes_ready", True, raising=False)

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=TerminalPayload.from_bytes(window.id, b"remote output\n").model_dump(),
                    )
                )
            )
            wait_for_condition(lambda: len(failures) == 1)
            wait_for_condition(lambda: len(es_client.indexed_documents) == 1)
    finally:
        test_client.close()

    async def load_terminal_state():
        async with client_agent_db.session_factory() as session:
            rows = (await session.execute(select(Event))).scalars().all()
            db_window = await session.get(VirtualWindow, window.id)
            return rows, db_window

    rows, db_window = asyncio.run(load_terminal_state())
    assert failures == [b"remote output\n"]
    assert rows == []
    assert db_window is not None
    assert db_window.terminal_last_output_at is not None
    assert es_client.indexed_documents[0]["document"]["text"] == "remote output\n"
