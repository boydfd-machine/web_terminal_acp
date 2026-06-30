from tests.integration.test_client_agent_ws_support import *

def test_client_agent_websocket_accepts_valid_client_and_acks_hello(client_agent_db):
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
                encode_agent_message(
                    AgentMessage(type="hello", client_id=client_agent_db.client_id)
                )
            )

            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["type"] == "hello_ack"
    assert response["client_id"] == str(client_agent_db.client_id)

def test_client_agent_websocket_rejects_invalid_token(client_agent_db):
    test_client = TestClient(app)
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/api/client-agent/ws",
                headers={
                    "X-Client-Id": str(client_agent_db.client_id),
                    "Authorization": "Bearer wrong-token",
                },
            ):
                pass
    finally:
        test_client.close()

    assert exc_info.value.code == 1008

def test_client_agent_bulk_websocket_does_not_start_workers_before_valid_hello(
    client_agent_db, monkeypatch
):
    worker_creations: list[str] = []

    def record_worker_creation(**kwargs):  # noqa: ANN003
        worker_creations.append(kwargs["queue_name"])

        async def parked_worker() -> None:
            await asyncio.sleep(60)

        return parked_worker()

    monkeypatch.setattr(
        client_agent_router,
        "_client_agent_message_worker",
        record_worker_creation,
    )
    test_client = TestClient(app)
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with test_client.websocket_connect(
                "/api/client-agent/bulk-ws",
                headers={
                    "X-Client-Id": str(client_agent_db.client_id),
                    "Authorization": f"Bearer {client_agent_db.token}",
                },
            ) as websocket:
                websocket.send_text(
                    encode_agent_message(
                        AgentMessage(type="hello", client_id=client_agent_db.client_id)
                    )
                )
                websocket.receive_json()
    finally:
        test_client.close()

    assert exc_info.value.code == 1003
    assert worker_creations == []

def test_client_agent_websocket_heartbeat_marks_client_online(client_agent_db):
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
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    async def load_client():
        async with client_agent_db.session_factory() as session:
            return await get_client(session, client_agent_db.client_id)

    db_client = asyncio.run(load_client())
    assert response["type"] == "heartbeat_ack"
    assert db_client is not None
    assert db_client.status is ClientStatus.ONLINE
    assert db_client.last_seen_at is not None
    assert db_client.connected_at is not None

def test_client_agent_websocket_heartbeat_survives_seen_update_failure(
    client_agent_db,
    monkeypatch,
):
    async def fail_seen_update(client_id: UUID, payload: dict[str, object]) -> bool:
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(
        client_agent_router,
        "_mark_client_seen_with_metadata",
        fail_seen_update,
    )

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
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            first_response = websocket.receive_json()
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            second_response = websocket.receive_json()
    finally:
        test_client.close()

    assert first_response["type"] == "heartbeat_ack"
    assert second_response["type"] == "heartbeat_ack"

def test_client_agent_websocket_hello_survives_seen_update_failure(
    client_agent_db,
    monkeypatch,
):
    async def fail_seen_update(client_id: UUID, payload: dict[str, object]) -> bool:
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(
        client_agent_router,
        "_mark_client_seen_with_metadata",
        fail_seen_update,
    )

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
                encode_agent_message(
                    AgentMessage(
                        type="hello",
                        client_id=client_agent_db.client_id,
                        payload={"hostname": "edge-host", "version": "9.9.9"},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["type"] == "hello_ack"

def test_client_agent_websocket_disconnect_cleanup_survives_offline_update_failure(
    client_agent_db,
    monkeypatch,
):
    async def fail_offline_update(client_id: UUID) -> bool:
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(
        client_agent_router,
        "_mark_client_disconnected_by_id",
        fail_offline_update,
    )

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
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["type"] == "heartbeat_ack"

def test_client_agent_websocket_inventory_survives_inventory_update_failure(
    client_agent_db,
    monkeypatch,
):
    async def fail_inventory_update(websocket, client_id: UUID, message: AgentMessage) -> bool:
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(
        client_agent_router,
        "_handle_inventory_message",
        fail_inventory_update,
    )

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
                encode_agent_message(
                    AgentMessage(
                        type="inventory",
                        client_id=client_agent_db.client_id,
                        payload={"tmux_windows": []},
                    )
                )
            )
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["type"] == "heartbeat_ack"

def test_client_agent_websocket_hello_records_client_version(client_agent_db):
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
                encode_agent_message(
                    AgentMessage(
                        type="hello",
                        client_id=client_agent_db.client_id,
                        payload={"hostname": "edge-host", "version": "0.2.3"},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    async def load_client():
        async with client_agent_db.session_factory() as session:
            return await get_client(session, client_agent_db.client_id)

    db_client = asyncio.run(load_client())
    assert response["type"] == "hello_ack"
    assert db_client is not None
    assert db_client.hostname == "edge-host"
    assert db_client.version == "0.2.3"

def test_client_agent_websocket_reconciles_inventory_and_marks_client_online(client_agent_db):
    async def create_disconnected_window():
        async with client_agent_db.session_factory() as session:
            client = await get_client(session, client_agent_db.client_id)
            assert client is not None
            client.status = ClientStatus.OFFLINE
            client.last_seen_at = None
            window = await create_window(
                session,
                client_agent_db.client_id,
                cwd="/tmp",
                shell_command="/bin/bash",
                remote_session_id="agent-session",
                remote_window_id="@7",
            )
            window.status = WindowStatus.disconnected
            await session.commit()
            return window.id

    window_id = asyncio.run(create_disconnected_window())

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
                encode_agent_message(
                    AgentMessage(
                        type="inventory",
                        client_id=client_agent_db.client_id,
                        payload={
                            "tmux_windows": [
                                {
                                    "local_window_id": str(window_id),
                                    "remote_session_id": "agent-session",
                                    "remote_window_id": "@7",
                                }
                            ]
                        },
                    )
                )
            )
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(type="heartbeat", client_id=client_agent_db.client_id)
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    async def load_state():
        async with client_agent_db.session_factory() as session:
            client = await get_client(session, client_agent_db.client_id)
            window = await session.get(VirtualWindow, window_id)
            return client, window

    db_client, window = asyncio.run(load_state())
    assert response["type"] == "heartbeat_ack"
    assert db_client is not None
    assert db_client.status is ClientStatus.ONLINE
    assert db_client.last_seen_at is not None
    assert window is not None
    assert window.status is WindowStatus.active
