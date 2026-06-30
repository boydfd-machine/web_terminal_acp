from tests.unit.test_summary_context_support import *

@pytest.mark.asyncio
async def test_collect_summary_context_filters_non_summary_session_content(session_factory):
    created_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add_all(
            [
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="cursor-session-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "user",
                        "content": "<user_info>\nOS Version: linux\n</user_info>",
                    },
                    fingerprint="cursor-user-info-context",
                    created_at=created_at,
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="cursor-session-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "user",
                        "content": "<user_query>\n排查 summary 输入过多的问题\n</user_query>",
                    },
                    fingerprint="cursor-real-user-query",
                    created_at=created_at + timedelta(seconds=1),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="cursor-session-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "user",
                        "content": "<encrypted>ciphertext</encrypted>",
                    },
                    fingerprint="cursor-encrypted-user-message",
                    created_at=created_at + timedelta(seconds=2),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
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
                    fingerprint="codex-agents-context",
                    created_at=created_at + timedelta(seconds=3),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="claude-session-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "tool-1",
                                    "content": "command output",
                                }
                            ],
                        },
                    },
                    fingerprint="claude-tool-result-user",
                    created_at=created_at + timedelta(seconds=4),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "exec_command",
                            "arguments": "{\"cmd\":\"pytest\"}",
                        },
                    },
                    fingerprint="codex-ordinary-tool-call",
                    created_at=created_at + timedelta(seconds=5),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "output": "pytest output",
                        },
                    },
                    fingerprint="codex-tool-result",
                    created_at=created_at + timedelta(seconds=6),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "reasoning",
                            "summary": [{"text": "internal thinking"}],
                        },
                    },
                    fingerprint="codex-reasoning",
                    created_at=created_at + timedelta(seconds=7),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "arguments": json.dumps(
                                {"questions": [{"question": "要覆盖标题和文件夹吗?"}]},
                                ensure_ascii=False,
                            ),
                        },
                    },
                    fingerprint="codex-ask-user-question",
                    created_at=created_at + timedelta(seconds=8),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="claude-session-1",
                    kind="assistant_message",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "需要确认一个选项"},
                                {
                                    "type": "tool_use",
                                    "name": "ask_user_question",
                                    "input": {"question": "保留旧字段兼容吗?"},
                                }
                            ],
                        },
                    },
                    fingerprint="claude-ask-user-question",
                    created_at=created_at + timedelta(seconds=9),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="codex-session-1",
                    kind="response_item",
                    virtual_window_id=window.id,
                    payload_json={
                        "provider": "codex",
                        "raw_type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "已完成过滤调整"}],
                        },
                    },
                    fingerprint="codex-assistant-reply",
                    created_at=created_at + timedelta(seconds=10),
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["payload"]["session_messages"] == [
        {"role": "user", "content": "排查 summary 输入过多的问题"},
        {"role": "tool_call", "name": "request_user_input", "content": "要覆盖标题和文件夹吗?"},
        {"role": "assistant", "content": "需要确认一个选项"},
        {"role": "tool_call", "name": "ask_user_question", "content": "保留旧字段兼容吗?"},
        {"role": "assistant", "content": "已完成过滤调整"},
    ]
    serialized = json.dumps(context, ensure_ascii=False)
    assert "<user_info>" not in serialized
    assert "<encrypted>" not in serialized
    assert "AGENTS.md instructions" not in serialized
    assert "command output" not in serialized
    assert "pytest output" not in serialized
    assert "internal thinking" not in serialized
    assert "exec_command" not in serialized
    assert "codex-session-1" not in serialized

@pytest.mark.asyncio
async def test_collect_summary_context_over_budget_keeps_recent_commands_and_marks_truncation(
    session_factory, monkeypatch
):
    class SmallBudgetSettings(Settings):
        terminal_summary_input_context_max_bytes: int = 1600

    monkeypatch.setattr(
        "app.repositories.summary_jobs.get_settings",
        lambda: SmallBudgetSettings(_env_file=None),
        raising=False,
    )
    captured_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        for sequence in range(20):
            session.add(
                command_event(
                    window,
                    sequence,
                    f"command-{sequence} " + ("x" * 120),
                    captured_at + timedelta(seconds=sequence),
                )
            )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    payload = context[0]["payload"]
    included_sequences = [command["sequence"] for command in payload["commands"]]
    assert included_sequences
    assert included_sequences == list(range(20 - len(included_sequences), 20))
    assert payload["truncation"] == {
        "total_commands": 20,
        "included_commands": len(included_sequences),
        "truncated": True,
        "budget_bytes": 1600,
    }

@pytest.mark.asyncio
async def test_collect_summary_context_uses_index_friendly_agent_event_reads(
    counted_session_factory,
):
    session_factory, statements = counted_session_factory
    created_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="agent-record",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint="agent-record-index-friendly",
                created_at=created_at,
            )
        )
        await session.commit()

    statements.clear()
    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        await collect_summary_context(session, window)

    event_reads = [
        statement
        for statement in statements
        if "FROM events" in statement and "SELECT events" in statement
    ]
    assert event_reads
    assert all("events.client_id" in statement for statement in event_reads)
    assert all("source_type IN" not in statement for statement in event_reads)

def test_settings_default_terminal_summary_input_context_max_bytes():
    assert Settings(_env_file=None).terminal_summary_input_context_max_bytes in {32768, 65536}
