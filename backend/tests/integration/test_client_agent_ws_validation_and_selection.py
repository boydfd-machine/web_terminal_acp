from tests.integration.test_client_agent_ws_support import *

def test_client_agent_websocket_rejects_cross_client_terminal_output(client_agent_db, monkeypatch):
    async def create_other_client_window():
        async with client_agent_db.session_factory() as session:
            other_client, _token = await create_client(
                session, name="other-terminal", runtime=ClientRuntime.remote
            )
            other_window = await create_window(session, other_client.id, cwd="/tmp", shell_command="/bin/bash")
            await session.commit()
            return other_window

    other_window = asyncio.run(create_other_client_window())
    broker = FakeTerminalBroker()
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)

    async def count_events():
        async with client_agent_db.session_factory() as session:
            return len((await session.execute(select(Event))).scalars().all())

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=other_window.id,
                        payload=TerminalPayload.from_bytes(other_window.id, b"wrong client\n").model_dump(),
                    )
                )
            )
    finally:
        test_client.close()

    assert broker.published == []
    assert asyncio.run(count_events()) == 0

def test_client_agent_websocket_rejects_ai_event_without_message_window_id(client_agent_db):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    payload = {
        "type": "assistant",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        request_id="missing-window",
                        payload={"provider": "claude", "payload": payload},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["type"] == "ai_event_ack"
    assert response["request_id"] == "missing-window"
    assert response["payload"]["ok"] is False
    assert "window_id is required" in response["payload"]["error"]

def test_client_agent_websocket_rejects_cross_client_ai_event_window(client_agent_db):
    async def create_other_client_window():
        async with client_agent_db.session_factory() as session:
            other_client, _token = await create_client(
                session, name="other", runtime=ClientRuntime.remote
            )
            other_window = await create_window(session, other_client.id, cwd="/tmp", shell_command="/bin/bash")
            await session.commit()
            return other_window

    other_window = asyncio.run(create_other_client_window())
    payload = {
        "type": "assistant",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(other_window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=other_window.id,
                        request_id="wrong-client-window",
                        payload={"provider": "claude", "payload": payload},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    async def count_events():
        async with client_agent_db.session_factory() as session:
            return len((await session.execute(select(Event))).scalars().all())

    assert response["type"] == "ai_event_ack"
    assert response["request_id"] == "wrong-client-window"
    assert response["payload"]["ok"] is False
    assert "window not found" in response["payload"]["error"]
    assert asyncio.run(count_events()) == 0

def test_client_agent_bulk_websocket_accepts_agent_work_presence(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = app.state.terminal_broker
    ui_event_hub = CaptureUiEventHub()
    monkeypatch.setattr(app.state, "ui_event_hub", ui_event_hub, raising=False)
    broker.published.clear()
    test_client = TestClient(app)
    async def latest_presence_at():
        async with client_agent_db.session_factory() as session:
            return await session.scalar(
                select(VirtualWindow.agent_presence_latest_at).where(VirtualWindow.id == window.id)
            )

    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as bulk_websocket:
            bulk_websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="agent_work_presence",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload={"providers": ["codex"], "reasons": ["tool_running"]},
                    )
                )
            )
            wait_for_condition(lambda: asyncio.run(latest_presence_at()) is not None)

            bulk_websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=TerminalPayload.from_bytes(window.id, b"still connected\n").model_dump(),
                    )
                )
            )
            wait_for_condition(
                lambda: broker.published == [(client_agent_db.client_id, window.id, b"still connected\n")]
                and asyncio.run(_event_count(client_agent_db.session_factory)) == 0
            )
    finally:
        test_client.close()

    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 0
    assert ui_event_hub.invalidations == [
        {
            "resources": ["window"],
            "client_id": client_agent_db.client_id,
            "window_id": window.id,
            "reason": "agent_work_presence",
        }
    ]

def test_client_agent_bulk_websocket_ignores_presence_for_deleted_window(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    missing_window_id = uuid4()
    broker = app.state.terminal_broker
    ui_event_hub = CaptureUiEventHub()
    monkeypatch.setattr(app.state, "ui_event_hub", ui_event_hub, raising=False)
    broker.published.clear()
    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as bulk_websocket:
            bulk_websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="agent_work_presence",
                        client_id=client_agent_db.client_id,
                        window_id=missing_window_id,
                        payload={"providers": ["codex"], "reasons": ["tool_running"]},
                    )
                )
            )
            bulk_websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_output",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload=TerminalPayload.from_bytes(window.id, b"still connected\n").model_dump(),
                    )
                )
            )
            wait_for_condition(
                lambda: broker.published == [(client_agent_db.client_id, window.id, b"still connected\n")]
            )
    finally:
        test_client.close()

    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 0
    assert ui_event_hub.invalidations == []

def test_client_agent_websocket_publishes_view_terminal_selection(client_agent_db):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    broker = app.state.terminal_broker
    broker.published.clear()
    view_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    test_client = TestClient(app)
    try:
        with test_client.websocket_connect(
            "/api/client-agent/ws",
            headers={
                "X-Client-Id": str(client_agent_db.client_id),
                "Authorization": f"Bearer {client_agent_db.token}",
            },
        ) as websocket:
            websocket.send_text(
                encode_agent_message(AgentMessage(type="hello", client_id=client_agent_db.client_id))
            )
            response = websocket.receive_json()
            assert response["type"] == "hello_ack"
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="terminal_selection",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        payload={"view_id": str(view_id)},
                    )
                )
            )
            wait_for_condition(lambda: len(broker.published) == 1)
    finally:
        test_client.close()

    client_id, published_view_id, raw_message = broker.published[0]
    assert client_id == client_agent_db.client_id
    assert published_view_id == view_id
    assert json.loads(raw_message.decode("utf-8")) == {
        "type": "terminal_selection",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "view_id": str(view_id),
    }

def test_control_websocket_rejects_bulk_messages(client_agent_db):
    test_client = TestClient(app)
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/api/client-agent/ws",
                headers={
                    "X-Client-Id": str(client_agent_db.client_id),
                    "Authorization": f"Bearer {client_agent_db.token}",
                },
            ) as websocket:
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(type="terminal_output", client_id=client_agent_db.client_id)
                    )
                )
                websocket.receive_json()
    finally:
        test_client.close()

    assert exc_info.value.code == 1003

def test_control_websocket_responds_while_bulk_terminal_output_handler_is_blocked(
    client_agent_db, monkeypatch
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    release_publish = threading.Event()
    broker = FakeTerminalBroker(block_publish=release_publish)
    monkeypatch.setattr(app.state, "terminal_broker", broker, raising=False)

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as bulk_websocket:
            with test_client.websocket_connect(
                "/api/client-agent/ws",
                headers={
                    "X-Client-Id": str(client_agent_db.client_id),
                    "Authorization": f"Bearer {client_agent_db.token}",
                },
            ) as control_websocket:
                bulk_websocket.send_text(
                    encode_agent_message(
                        AgentMessage(
                            type="terminal_output",
                            client_id=client_agent_db.client_id,
                            window_id=window.id,
                            payload=TerminalPayload.from_bytes(window.id, b"blocked output\n").model_dump(),
                        )
                    )
                )
                assert broker.publish_started.wait(timeout=2.0)

                control_websocket.send_text(
                    encode_agent_message(
                        AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                    )
                )
                response = control_websocket.receive_json()
                release_publish.set()
                wait_for_condition(lambda: len(broker.published) == 1)
    finally:
        release_publish.set()
        test_client.close()

    assert response["type"] == "heartbeat_ack"
    assert broker.published == [(client_agent_db.client_id, window.id, b"blocked output\n")]
