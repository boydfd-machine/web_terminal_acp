from tests.integration.test_window_api_support import *

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_returns_minimal_messages(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-session-1",
            virtual_window_id=window_id,
        )
        session.add(ai_session)
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "response_item",
                        "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                    },
                    fingerprint="agent-record-chat-user",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "response_item",
                        "payload": {"type": "function_call", "name": "bash", "arguments": "{\"cmd\":\"ls\"}"},
                    },
                    fingerprint="agent-record-chat-tool",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "response_item",
                        "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "done"}]},
                    },
                    fingerprint="agent-record-chat-agent",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="event_msg",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "event_msg",
                        "payload": {"type": "agent_message", "message": "done"},
                    },
                    fingerprint="agent-record-chat-agent-duplicate",
                    created_at=base_time + timedelta(milliseconds=3),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?messages_limit=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["window_id"] == str(window_id)
    assert [(item["role"], item["body"]) for item in body["messages"]] == [("user", "hello")]
    assert "payload_json" not in body["messages"][0]
    assert body["messages_total"] == 2
    assert body["messages_limit"] == 1
    assert body["messages_offset"] == 0
    assert body["messages_has_more"] is True


@pytest.mark.asyncio
async def test_get_window_agent_record_chat_dedupes_codex_agent_message_with_different_source_id(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-turn-1",
                    kind="event_msg",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "event_msg",
                        "payload": {"type": "agent_message", "message": "done"},
                    },
                    fingerprint="agent-record-chat-agent-event-msg",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="msg_codex_response_1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "id": "msg_codex_response_1",
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                        },
                    },
                    fingerprint="agent-record-chat-agent-response-item",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat")

    assert response.status_code == 200
    body = response.json()
    assert [(item["role"], item["body"]) for item in body["messages"]] == [("agent", "done")]
    assert body["messages_total"] == 1
    assert body["messages_has_more"] is False


@pytest.mark.asyncio
async def test_get_window_agent_record_chat_stops_after_requested_page(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-session-1",
            virtual_window_id=window_id,
        )
        session.add(ai_session)
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload(f"message {index}"),
                    fingerprint=f"agent-record-chat-page-{index}",
                    created_at=base_time + timedelta(milliseconds=index),
                )
                for index in range(600)
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?messages_limit=30"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["body"] for item in body["messages"]] == [f"message {index}" for index in range(30)]
    assert body["messages_total"] == 31
    assert body["messages_total_exact"] is False
    assert body["messages_has_more"] is True

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_can_return_latest_page(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-session-latest",
            virtual_window_id=window_id,
        )
        session.add(ai_session)
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-latest",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json=codex_user_message_payload(f"message {index}"),
                    fingerprint=f"agent-record-chat-latest-{index}",
                    created_at=base_time + timedelta(milliseconds=index),
                )
                for index in range(40)
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat"
        "?messages_limit=3&messages_order=latest"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["body"] for item in body["messages"]] == ["message 37", "message 38", "message 39"]
    assert body["messages_total"] == 40
    assert body["messages_total_exact"] is True
    assert body["messages_offset"] == 0
    assert body["messages_has_more"] is True

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_filters_by_role(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(client_id),
            provider="codex",
            source_id="codex-session-1",
            virtual_window_id=window_id,
        )
        session.add(ai_session)
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "hello"}],
                        },
                    },
                    fingerprint="agent-record-chat-role-user",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.codex_trace,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    ai_session_id=ai_session.id,
                    payload_json={
                        "raw_type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                        },
                    },
                    fingerprint="agent-record-chat-role-agent",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?role=agent"
    )

    assert response.status_code == 200
    body = response.json()
    assert [(item["role"], item["body"]) for item in body["messages"]] == [("agent", "done")]
    assert body["messages_total"] == 1
    assert body["messages_has_more"] is False

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_distinguishes_claude_subagent_messages(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        base_time = datetime.now(timezone.utc)
        main_session = AiSession(
            client_id=UUID(client_id),
            provider="claude_code",
            source_id="main-session-1",
            virtual_window_id=window_id,
            created_at=base_time,
            updated_at=base_time,
        )
        sub_session = AiSession(
            client_id=UUID(client_id),
            provider="claude_code",
            source_id="agent-subagent-1",
            source_path="/tmp/main-session-1/subagents/agent-subagent-1.jsonl",
            virtual_window_id=window_id,
            created_at=base_time + timedelta(milliseconds=1),
            updated_at=base_time + timedelta(milliseconds=1),
        )
        session.add_all([main_session, sub_session])
        await session.flush()
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="main-session-1",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    ai_session_id=main_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call-subagent-1",
                                    "name": "Agent",
                                    "input": {"description": "Return one", "prompt": "Return exactly: 1"},
                                }
                            ],
                        },
                        "subagent_tool_use_results": [
                            {"tool_use_id": "call-subagent-1", "agent_id": "subagent-1"}
                        ],
                    },
                    fingerprint="agent-record-chat-subagent-call",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="agent-subagent-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    ai_session_id=sub_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "sessionId": "main-session-1",
                        "agentId": "subagent-1",
                        "isSidechain": True,
                        "subagent": {"toolUseId": "call-subagent-1"},
                        "message": {"role": "user", "content": "Return exactly: 1"},
                    },
                    fingerprint="agent-record-chat-subagent-prompt",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="main-session-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    ai_session_id=main_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [
                                {"type": "tool_result", "tool_use_id": "call-subagent-1", "content": "1"}
                            ],
                        },
                        "toolUseResult": {"agentId": "subagent-1", "toolUseId": "call-subagent-1"},
                    },
                    fingerprint="agent-record-chat-subagent-result",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="agent-subagent-1",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    ai_session_id=sub_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "assistant",
                        "sessionId": "main-session-1",
                        "agentId": "subagent-1",
                        "isSidechain": True,
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "subagent internal answer"}]},
                    },
                    fingerprint="agent-record-chat-subagent-internal-answer",
                    created_at=base_time + timedelta(milliseconds=3),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat")

    assert response.status_code == 200
    body = response.json()
    assert [(item["role"], item["agent_message_type"], item["body"]) for item in body["messages"]] == [
        ("agent", "subagent_call", "Description: Return one\n\nReturn exactly: 1"),
        ("agent", "subagent_result", "1"),
        ("agent", "agent", "subagent internal answer"),
    ]
    assert body["messages"][0]["target_session_id"] == str(sub_session.id)
    assert body["messages"][0]["target_session_source_id"] == "agent-subagent-1"
    assert body["messages_total"] == 3

    filtered = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?role=agent"
    )
    assert filtered.status_code == 200
    assert [(item["agent_message_type"], item["body"]) for item in filtered.json()["messages"]] == [
        ("agent", "subagent internal answer")
    ]

    subagent_calls = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?role=subagent_call"
    )
    assert subagent_calls.status_code == 200
    assert [item["agent_message_type"] for item in subagent_calls.json()["messages"]] == ["subagent_call"]

    main_chat = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?session_id={main_session.id}"
    )
    assert main_chat.status_code == 200
    assert [(item["agent_message_type"], item["body"]) for item in main_chat.json()["messages"]] == [
        ("subagent_call", "Description: Return one\n\nReturn exactly: 1"),
        ("subagent_result", "1"),
    ]

    subagent_chat = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat?session_id={sub_session.id}"
    )
    assert subagent_chat.status_code == 200
    assert [(item["agent_message_type"], item["body"]) for item in subagent_chat.json()["messages"]] == [
        ("subagent_call", "Return exactly: 1"),
        ("agent", "subagent internal answer")
    ]
    assert subagent_chat.json()["messages"][0]["subagent_tool_use_id"] == "call-subagent-1"

    subagent_detail = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record/detail?session_id={sub_session.id}"
    )
    assert subagent_detail.status_code == 200
    detail_body = subagent_detail.json()
    assert [item["id"] for item in detail_body["sessions"]] == [str(main_session.id), str(sub_session.id)]
    assert [item["ai_session_id"] for item in detail_body["events"]] == [str(sub_session.id), str(sub_session.id)]
