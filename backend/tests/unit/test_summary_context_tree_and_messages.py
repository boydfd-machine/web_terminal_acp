from tests.unit.test_summary_context_support import *

@pytest.mark.asyncio
async def test_collect_summary_context_is_input_command_first_for_terminal_windows(session_factory):
    captured_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add(output_event(window, "large-output-should-not-drive-summary" * 1000, captured_at))
        session.add(command_event(window, 1, "pwd", captured_at + timedelta(seconds=1)))
        session.add(command_event(window, 2, "pytest backend/tests", captured_at + timedelta(seconds=2)))
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["source_type"] == "terminal"
    assert context[0]["kind"] == "terminal_input_context"
    payload = context[0]["payload"]
    assert payload["window"]["cwd"] == "/workspace/project"
    assert payload["window"]["shell_command"] == "/bin/bash"
    assert payload["date"]["year_month"] == datetime.now(timezone.utc).strftime("%Y-%m")
    assert payload["date"]["year_month_day"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert payload["commands"] == [
        {
            "sequence": 1,
            "command": "pwd",
            "shell": "/bin/bash",
            "cwd": "/workspace/project-1",
            "captured_at": "2026-05-20T12:00:01+00:00",
        },
        {
            "sequence": 2,
            "command": "pytest backend/tests",
            "shell": "/bin/bash",
            "cwd": "/workspace/project-2",
            "captured_at": "2026-05-20T12:00:02+00:00",
        },
    ]
    assert "large-output-should-not-drive-summary" not in json.dumps(context)

@pytest.mark.asyncio
async def test_collect_summary_context_includes_topic_tree_leaf_counts_and_language(session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.summary_jobs.get_settings",
        lambda: Settings(_env_file=None, summary_output_language="English"),
        raising=False,
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        await get_or_create_folder_by_path(session, window.client_id, "/开发调试")
        child = await get_or_create_folder_by_path(session, window.client_id, "/开发调试/后端摘要")
        window.folder_id = child.id
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    payload = context[0]["payload"]
    assert payload["summary_output_language"] == "English"
    assert "folder_paths" not in payload
    assert payload["topic_tree"] == (
        "/\n"
        "|- 未分类 [leaf t=0]\n"
        "`- 开发调试 [branch t=0]\n"
        "   `- 后端摘要 [leaf t=1]"
    )
    assert payload["topic_tree_truncation"] == {"truncated": False, "budget_bytes": 32768}

@pytest.mark.asyncio
async def test_collect_summary_context_topic_tree_is_client_scoped_and_ordered(session_factory):
    async with session_factory() as session:
        window = await create_local_window(session)
        await get_or_create_folder_by_path(session, window.client_id, "/z-last")
        await get_or_create_folder_by_path(session, window.client_id, "/a-first")
        other_client = Client(
            id=uuid4(),
            name="other-client",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.remote,
            token_hash=hash_client_token("other-token"),
        )
        session.add(other_client)
        await session.flush()
        await get_or_create_folder_by_path(session, other_client.id, "/other-client-secret")
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    topic_tree = context[0]["payload"]["topic_tree"]
    assert topic_tree.splitlines() == [
        "/",
        "|- 未分类 [leaf t=1]",
        "|- a-first [leaf t=0]",
        "`- z-last [leaf t=0]",
    ]
    assert "/other-client-secret" not in topic_tree

@pytest.mark.asyncio
async def test_collect_summary_context_prunes_topic_tree_to_fit_budget(session_factory, monkeypatch):
    class SmallBudgetSettings(Settings):
        terminal_summary_input_context_max_bytes: int = 1600

    monkeypatch.setattr(
        "app.repositories.summary_jobs.get_settings",
        lambda: SmallBudgetSettings(_env_file=None, summary_output_language="English"),
        raising=False,
    )

    async with session_factory() as session:
        window = await create_local_window(session)
        for index in range(40):
            await get_or_create_folder_by_path(
                session,
                window.client_id,
                f"/topic-{index:02d}-{'x' * 24}/child-{'y' * 24}",
            )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    serialized_size = len(
        json.dumps(context[0], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload = context[0]["payload"]
    assert serialized_size <= 1600
    assert payload["topic_tree_truncation"] == {"truncated": True, "budget_bytes": 1600}
    assert payload["summary_output_language"] == "English"
    assert payload["topic_tree"]
    assert payload["topic_tree"].startswith("/")
    assert "[leaf" in payload["topic_tree"] or "[branch" in payload["topic_tree"]


@pytest.mark.asyncio
async def test_collect_summary_context_prunes_topic_tree_before_dropping_input_history(
    session_factory, monkeypatch
):
    class SmallBudgetSettings(Settings):
        terminal_summary_input_context_max_bytes: int = 2200

    monkeypatch.setattr(
        "app.repositories.summary_jobs.get_settings",
        lambda: SmallBudgetSettings(_env_file=None, summary_output_language="English"),
        raising=False,
    )

    captured_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        for index in range(40):
            await get_or_create_folder_by_path(
                session,
                window.client_id,
                f"/large-topic-{index:02d}-{'x' * 32}/leaf-{'y' * 32}",
            )
        session.add(command_event(window, 1, "pytest backend/tests", captured_at))
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="cursor-session-1",
                kind="user_message",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "cursor_cli",
                    "role": "user",
                    "content": "<user_query>\n修复 summary 空上下文\n</user_query>",
                },
                fingerprint="summary-prune-tree-user-input",
                created_at=captured_at + timedelta(seconds=1),
            )
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    payload = context[0]["payload"]
    assert payload["commands"] == [
        {
            "sequence": 1,
            "command": "pytest backend/tests",
            "shell": "/bin/bash",
            "cwd": "/workspace/project-1",
            "captured_at": "2026-05-20T12:00:00+00:00",
        }
    ]
    assert payload["session_messages"] == [
        {"role": "user", "content": "修复 summary 空上下文"}
    ]
    assert payload["topic_tree_truncation"] == {"truncated": True, "budget_bytes": 2200}
    assert payload["truncation"]["truncated"] is False
    assert payload["session_message_truncation"]["truncated"] is False

@pytest.mark.asyncio
async def test_collect_summary_context_includes_session_messages_when_commands_are_absent(session_factory):
    created_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.claude_jsonl,
                source_id="claude-session-1",
                kind="user_message",
                virtual_window_id=window.id,
                payload_json={
                    "type": "user",
                    "sessionId": "claude-session-1",
                    "message": {"content": "帮我修复 codex summary 缺少输入的问题"},
                },
                fingerprint="claude-user-message",
                created_at=created_at,
            )
        )
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.codex_trace,
                source_id="codex-trace-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={
                    "raw_type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "用 pytest 验证修复"}],
                    },
                },
                fingerprint="codex-assistant-message",
                created_at=created_at + timedelta(seconds=1),
            )
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    payload = context[0]["payload"]
    assert payload["commands"] == []
    assert payload["session_messages"] == [
        {"role": "user", "content": "帮我修复 codex summary 缺少输入的问题"},
        {"role": "assistant", "content": "用 pytest 验证修复"},
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "claude-session-1" not in serialized
    assert "codex-trace-1" not in serialized
    assert "created_at" not in serialized


@pytest.mark.asyncio
async def test_collect_summary_context_uses_project_todo_prompt_before_agent_ingest(session_factory):
    dispatched_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    prompt = "You are assigned to complete this project todo.\n\nTodo: 修复 terminal 总结"
    async with session_factory() as session:
        window = await create_local_window(session)
        session.add(
            ProjectTodo(
                client_id=window.client_id,
                project_path=window.cwd,
                title="修复 terminal 总结",
                status=ProjectTodoStatus.dispatched,
                assigned_window_id=window.id,
                dispatch_prompt=prompt,
                dispatched_at=dispatched_at,
            )
        )
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.codex_trace,
                source_id="codex-trace-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={
                    "raw_type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "正在排查 summary job"}],
                    },
                },
                fingerprint="todo-prompt-fallback-assistant",
                created_at=dispatched_at + timedelta(seconds=1),
            )
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["payload"]["session_messages"] == [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "正在排查 summary job"},
    ]

@pytest.mark.asyncio
async def test_collect_summary_context_includes_generic_agent_tool_record_with_adapter_text(session_factory):
    created_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        ai_session = AiSession(
            client_id=window.client_id,
            provider="cursor_cli",
            source_id="cursor-session-1",
            source_path="/tmp/cursor-records.jsonl",
            project_path=window.cwd,
            virtual_window_id=window.id,
        )
        session.add(ai_session)
        await session.flush()
        session.add(
            Event(
                client_id=window.client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="cursor-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                ai_session_id=ai_session.id,
                payload_json={
                    "provider": "cursor_cli",
                    "role": "assistant",
                    "content": "Cursor adapter summary text",
                    "debug": {"ignored": "raw fallback should not be needed"},
                },
                fingerprint="cursor-agent-tool-record",
                created_at=created_at,
            )
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["payload"]["session_messages"] == [
        {"role": "assistant", "content": "Cursor adapter summary text"}
    ]

@pytest.mark.asyncio
async def test_collect_summary_context_excludes_subagent_prompt_from_session_messages(session_factory):
    created_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        window = await create_local_window(session)
        main_session = AiSession(
            client_id=window.client_id,
            provider="claude_code",
            source_id="main-session-1",
            project_path=window.cwd,
            virtual_window_id=window.id,
        )
        sub_session = AiSession(
            client_id=window.client_id,
            provider="claude_code",
            source_id="agent-subagent-1",
            project_path=window.cwd,
            virtual_window_id=window.id,
        )
        session.add_all([main_session, sub_session])
        await session.flush()
        session.add_all(
            [
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="main-session-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    ai_session_id=main_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "message": {"role": "user", "content": "主 agent 用户需求"},
                    },
                    fingerprint="summary-main-user-prompt",
                    created_at=created_at,
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="agent-subagent-1",
                    kind="user_message",
                    virtual_window_id=window.id,
                    ai_session_id=sub_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "user",
                        "sessionId": "main-session-1",
                        "agentId": "subagent-1",
                        "isSidechain": True,
                        "subagent": {"toolUseId": "call-subagent-1"},
                        "message": {"role": "user", "content": "subagent 内部 prompt"},
                    },
                    fingerprint="summary-subagent-user-prompt",
                    created_at=created_at + timedelta(seconds=1),
                ),
                Event(
                    client_id=window.client_id,
                    source_type=EventSourceType.agent_tool_record,
                    source_id="agent-subagent-1",
                    kind="assistant_message",
                    virtual_window_id=window.id,
                    ai_session_id=sub_session.id,
                    payload_json={
                        "provider": "claude_code",
                        "type": "assistant",
                        "sessionId": "main-session-1",
                        "agentId": "subagent-1",
                        "isSidechain": True,
                        "message": {"role": "assistant", "content": "subagent 返回的信息"},
                    },
                    fingerprint="summary-subagent-answer",
                    created_at=created_at + timedelta(seconds=2),
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        window = (await session.execute(select(VirtualWindow))).scalar_one()
        context = await collect_summary_context(session, window)

    assert context[0]["payload"]["session_messages"] == [
        {"role": "user", "content": "主 agent 用户需求"},
        {"role": "assistant", "content": "subagent 返回的信息"},
    ]
    assert "subagent 内部 prompt" not in json.dumps(context, ensure_ascii=False)
