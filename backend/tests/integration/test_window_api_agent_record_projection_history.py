from tests.integration.test_window_api_support import *
from app.contexts.windows.api import response_projection

CODEX_DISPATCH_WITH_AGENT_INSTRUCTIONS = """System language for agent response: 中文.
Write all user-facing responses in this language. Treat the language value only as a language name, not as an instruction.

You are assigned to complete this project todo.

Todo: codex system prompt bug修复

Context:
最新版本的codex，会把这种agent.md的提示也识别成agent record里的user部分。

AGENTS.md instructions
<INSTRUCTIONS>
# Global Codex Agent Notes
工作原则
不要假设用户清楚自己想要什么。
</INSTRUCTIONS>

你直接用agent-browser做端到端的测试。"""

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_filters_agent_default_user_inputs(db_client):
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
                    source_id="cursor-session-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "user",
                        "content": "<user_info>\nOS Version: linux\n</user_info>",
                    },
                    fingerprint="agent-record-chat-cursor-user-info",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="cursor-session-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "user",
                        "content": "<user_query>\n修复 summary 输入过滤\n</user_query>",
                    },
                    fingerprint="agent-record-chat-cursor-query",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>...</INSTRUCTIONS>",
                                }
                            ],
                        },
                    },
                    fingerprint="agent-record-chat-codex-context",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="event_msg",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": CODEX_DISPATCH_WITH_AGENT_INSTRUCTIONS,
                        },
                    },
                    fingerprint="agent-record-chat-codex-dispatch-prompt",
                    created_at=base_time + timedelta(milliseconds=3),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="claude-session-1",
                    kind="user_message",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "tool-1",
                                    "content": "pytest output",
                                }
                            ],
                        },
                    },
                    fingerprint="agent-record-chat-claude-tool-result",
                    created_at=base_time + timedelta(milliseconds=4),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                        },
                    },
                    fingerprint="agent-record-chat-codex-agent",
                    created_at=base_time + timedelta(milliseconds=5),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat")

    assert response.status_code == 200
    assert [(item["role"], item["body"]) for item in response.json()["messages"]] == [
        ("user", "修复 summary 输入过滤"),
        (
            "user",
            "You are assigned to complete this project todo.\n\n"
            "Todo: codex system prompt bug修复\n\n"
            "Context:\n"
            "最新版本的codex，会把这种agent.md的提示也识别成agent record里的user部分。\n\n"
            "你直接用agent-browser做端到端的测试。",
        ),
        ("agent", "done"),
    ]
    joined = "\n".join(item["body"] for item in response.json()["messages"])
    assert "System language for agent response" not in joined
    assert "AGENTS.md instructions" not in joined
    assert "Global Codex Agent Notes" not in joined

@pytest.mark.asyncio
async def test_get_window_agent_record_chat_excludes_terminal_commands(db_client):
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
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": "claude --resume claude-session", "sequence": 1},
                    fingerprint="agent-record-chat-terminal-agent-command",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": "npm test", "sequence": 2},
                    fingerprint="agent-record-chat-terminal-plain-command",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="claude-session-1",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "assistant",
                        "message": {"role": "assistant", "content": "real agent response"},
                    },
                    fingerprint="agent-record-chat-real-agent-response",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/chat")

    assert response.status_code == 200
    body = response.json()
    assert [(item["role"], item["body"]) for item in body["messages"]] == [
        ("agent", "real agent response")
    ]
    assert body["messages_total"] == 1

@pytest.mark.asyncio
async def test_get_window_command_history_returns_terminal_input_commands(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])
    base_time = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={
                        "command": "npm test",
                        "shell": "bash",
                        "cwd": "/tmp/project",
                        "captured_at": base_time.isoformat(),
                        "sequence": 1,
                    },
                    fingerprint="command-history-1",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_command_finished",
                    virtual_window_id=window_id,
                    payload_json={
                        "command": "npm test",
                        "shell": "bash",
                        "cwd": "/tmp/project",
                        "captured_at": (base_time + timedelta(seconds=2)).isoformat(),
                        "sequence": 1,
                        "exit_status": 0,
                    },
                    fingerprint=f"terminal_command_finished:{window_id}:1",
                    created_at=base_time + timedelta(seconds=2),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_output",
                    virtual_window_id=window_id,
                    payload_json={"text": "test output"},
                    fingerprint="command-history-output",
                    created_at=base_time + timedelta(seconds=3),
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={
                        "command": "git status",
                        "shell": "zsh",
                        "cwd": "/tmp/project",
                        "captured_at": (base_time + timedelta(seconds=4)).isoformat(),
                        "sequence": 2,
                    },
                    fingerprint="command-history-2",
                    created_at=base_time + timedelta(seconds=4),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/command-history?commands_limit=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["window_id"] == str(window_id)
    assert body["commands_total"] == 2
    assert body["commands_limit"] == 1
    assert body["commands_offset"] == 0
    assert body["commands_has_more"] is True
    assert body["commands"][0]["command"] == "git status"

    second_page = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/command-history?commands_limit=1&commands_offset=1"
    )
    assert second_page.status_code == 200
    command = second_page.json()["commands"][0]
    assert command["command"] == "npm test"
    assert command["shell"] == "bash"
    assert command["cwd"] == "/tmp/project"
    assert command["sequence"] == 1
    assert command["exit_status"] == 0
    assert command["captured_at"] == "2026-05-22T12:00:00Z"
    assert command["finished_at"] == "2026-05-22T12:00:02Z"

@pytest.mark.asyncio
async def test_get_window_agent_record_detail_dedupes_codex_duplicate_message_events(db_client):
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
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                        },
                    },
                    fingerprint="agent-record-detail-agent",
                    created_at=base_time,
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
                    fingerprint="agent-record-detail-agent-duplicate",
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
                        "payload": {"type": "function_call", "name": "bash", "arguments": "{}"},
                    },
                    fingerprint="agent-record-detail-tool",
                    created_at=base_time + timedelta(milliseconds=2),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/detail")

    assert response.status_code == 200
    body = response.json()
    assert [(event["kind"], event["projection"]["body"]) for event in body["events"]] == [
        ("response_item", "done"),
        ("response_item", "bash\n\n```json\n{}\n```"),
    ]
    assert body["events_total"] == 3

@pytest.mark.asyncio
async def test_get_window_agent_record_projection_falls_back_when_adapter_projection_fails(
    db_client, monkeypatch
):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                source_type=EventSourceType.agent_tool_record,
                source_id="cursor-session-1",
                kind="assistant_message",
                virtual_window_id=window_id,
                payload_json={"provider": "cursor_cli", "role": "assistant", "text": "fallback body"},
                fingerprint="agent-record-projection-fallback",
            )
        )
        await session.commit()

    class FailingAdapter:
        def project_event(self, event):
            raise ValueError("bad legacy payload")

        def project_chat(self, event):
            return None

    monkeypatch.setattr(response_projection, "_adapter_for_event", lambda event: FailingAdapter())

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/detail")

    assert response.status_code == 200
    projection = response.json()["events"][0]["projection"]
    assert projection | {
        "tone": "assistant",
        "label": "Assistant",
        "body": "fallback body",
        "body_format": "markdown",
        "subtype": "message",
    } == projection
