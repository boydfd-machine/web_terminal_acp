from tests.integration.test_window_api_support import *

@pytest.mark.asyncio
async def test_windows_activity_does_not_notify_for_agent_open_close_without_result(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        finished_at = started_at + timedelta(seconds=30)
        session.add_all([
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "claude", "sequence": 9},
                fingerprint=f"terminal_input_command:{window.id}:claude-open",
                created_at=started_at,
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 9, "exit_status": 0},
                fingerprint=f"terminal_command_finished:{window.id}:claude-close",
                created_at=finished_at,
            ),
        ])
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["last_agent_task_completed_at"] is None
    assert activity_window["last_agent_task_status"] is None

@pytest.mark.asyncio
async def test_windows_activity_notifies_for_explicit_agent_completion(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        completed_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "event_msg",
                    "payload": {"type": "task_completed"},
                },
                fingerprint=f"agent_tool_record:{window.id}:codex-complete",
                created_at=completed_at,
            )
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "FINISHED"
    assert activity_window["last_agent_task_status"] == "FINISHED"
    assert activity_window["last_agent_task_status_at"] is not None

@pytest.mark.asyncio
async def test_windows_activity_notifies_for_codex_task_complete_event(db_client):
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        completed_at = now - timedelta(seconds=30)
        session.add_all(
            [
                Event(
                    client_id=client.id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json=codex_message_payload(
                        "finished",
                        timestamp=completed_at - timedelta(milliseconds=45),
                    ),
                    fingerprint=f"agent_tool_record:{window.id}:codex-final-message",
                    created_at=completed_at - timedelta(milliseconds=45),
                ),
                Event(
                    client_id=client.id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session",
                    kind="event_msg",
                    virtual_window_id=window.id,
                    payload_json=codex_completion_payload(
                        event_type="task_complete",
                        timestamp=completed_at,
                    ),
                    fingerprint=f"agent_tool_record:{window.id}:codex-task-complete",
                    created_at=completed_at,
                ),
            ]
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "FINISHED"
    assert activity_window["last_agent_task_status"] == "FINISHED"
    assert activity_window["last_agent_task_status_at"] is not None

@pytest.mark.asyncio
async def test_windows_activity_notifies_for_agent_abort(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        now = datetime.now(timezone.utc)
        output_at = now - timedelta(minutes=61)
        session.add_all([
            Event(
                client_id=client.id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'hang'", "sequence": 10},
                fingerprint=f"terminal_input_command:{window.id}:codex-hang",
                created_at=now - timedelta(minutes=62),
            ),
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "still running"}],
                    },
                },
                fingerprint=f"agent_tool_record:{window.id}:codex-hang-output",
                created_at=output_at,
            ),
        ])
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/activity")

    assert response.status_code == 200
    activity_window = next(
        item for item in response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "ABORTED"
    assert activity_window["last_agent_task_status"] == "ABORTED"
    assert activity_window["last_agent_task_status_at"] is not None

@pytest.mark.asyncio
async def test_terminal_notifications_are_backend_stateful(db_client):
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        completed_at = now - timedelta(seconds=30)
        session.add(
            Event(
                client_id=client.id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json=codex_completion_payload(timestamp=completed_at),
                fingerprint=f"agent_tool_record:{window.id}:codex-notification-complete",
                created_at=completed_at,
            )
        )
        window_id = str(window.id)
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/terminal-notifications")

    assert response.status_code == 200
    [notification] = response.json()["notifications"]
    assert notification["window_id"] == window_id
    assert notification["status"] == "FINISHED"
    assert notification["read"] is False

    read_response = await db_client.post(
        f"/api/clients/{client_id}/terminal-notifications/read",
        json={
            "window_id": window_id,
            "completed_at": notification["completed_at"],
        },
    )

    assert read_response.status_code == 200
    [read_notification] = read_response.json()["notifications"]
    assert read_notification["id"] == notification["id"]
    assert read_notification["read"] is True

    dismiss_response = await db_client.post(
        f"/api/clients/{client_id}/terminal-notifications/dismiss",
        json={
            "window_id": window_id,
            "completed_at": notification["completed_at"],
        },
    )

    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["notifications"] == []
    assert (await db_client.get(f"/api/clients/{client_id}/terminal-notifications")).json()["notifications"] == []

    stale_response = await db_client.post(
        f"/api/clients/{client_id}/terminal-notifications/read",
        json={
            "window_id": window_id,
            "completed_at": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert stale_response.status_code == 404

@pytest.mark.asyncio
async def test_terminal_notifications_clear_hides_current_notifications(db_client):
    client_id = await get_local_client_id(db_client)
    now = datetime.now(timezone.utc)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        first = await create_window(session, client.id, cwd="/tmp/one", shell_command="/bin/bash")
        second = await create_window(session, client.id, cwd="/tmp/two", shell_command="/bin/bash")
        for index, window in enumerate((first, second)):
            completed_at = now - timedelta(seconds=30 + index)
            session.add(
                Event(
                    client_id=client.id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id=f"codex-session-{index}",
                    kind="event_msg",
                    virtual_window_id=window.id,
                    payload_json=codex_completion_payload(timestamp=completed_at),
                    fingerprint=f"agent_tool_record:{window.id}:codex-clear-complete",
                    created_at=completed_at,
                )
            )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/terminal-notifications")
    assert response.status_code == 200
    assert len(response.json()["notifications"]) == 2

    clear_response = await db_client.delete(f"/api/clients/{client_id}/terminal-notifications")

    assert clear_response.status_code == 200
    assert clear_response.json()["notifications"] == []
    assert (await db_client.get(f"/api/clients/{client_id}/terminal-notifications")).json()["notifications"] == []
