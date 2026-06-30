from tests.unit.test_terminal_work_status_support import *

@pytest.mark.asyncio
async def test_load_tree_window_activity_allows_late_agent_output_within_delay_window(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(seconds=5)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'done'", "sequence": 4},
                fingerprint="terminal-input-codex-late-output-tree",
                created_at=now - timedelta(seconds=40),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 4, "exit_status": 0},
                fingerprint="terminal-finished-codex-late-output-tree",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("late watcher write"),
                fingerprint="codex-agent-output-after-shell-exit-tree",
                created_at=now - timedelta(seconds=5),
            ),
        ]
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "WORKING"
    assert activity.work_statuses[window.id].last_activity_at == now - timedelta(seconds=5)
    assert activity.work_statuses[window.id].last_working_activity_at == now - timedelta(seconds=5)
    assert window.id not in activity.last_agent_task_status

@pytest.mark.asyncio
async def test_load_tree_window_activity_ignores_late_agent_output_after_delay_window(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(seconds=5)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'done'", "sequence": 5},
                fingerprint="terminal-input-codex-late-output-tree-delay",
                created_at=now - timedelta(seconds=80),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 5, "exit_status": 0},
                fingerprint="terminal-finished-codex-late-output-tree-delay",
                created_at=now - timedelta(seconds=60),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("late watcher write"),
                fingerprint="codex-agent-output-after-shell-exit-tree-delay",
                created_at=now - timedelta(seconds=5),
            ),
        ]
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "RECENT_ACTIVE"
    assert activity.work_statuses[window.id].last_activity_at == now - timedelta(seconds=60)
    assert activity.work_statuses[window.id].last_working_activity_at is None
    assert window.id not in activity.last_agent_task_status

@pytest.mark.asyncio
async def test_load_tree_window_activity_reports_finished_notification_status(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=30)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_completed_at = completed_at
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json=claude_completion_payload(),
            fingerprint="claude-agent-finished-status",
            created_at=completed_at,
        )
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "FINISHED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at

@pytest.mark.asyncio
async def test_load_work_status_keeps_claude_finished_after_metadata_events(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Claude", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=30)
    metadata_at = now - timedelta(seconds=10)
    window.agent_activity_latest_at = metadata_at
    window.agent_activity_latest_event_id = uuid4()
    window.agent_activity_latest_completed_at = completed_at
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="system_message",
                virtual_window_id=window.id,
                payload_json=claude_turn_duration_payload(timestamp=completed_at),
                fingerprint="claude-completed-before-metadata",
                created_at=completed_at,
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="last-prompt",
                virtual_window_id=window.id,
                payload_json=claude_metadata_payload("last-prompt"),
                fingerprint="claude-last-prompt-after-completion",
                created_at=metadata_at,
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    assert status.last_activity_at == completed_at
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at


@pytest.mark.asyncio
async def test_load_work_status_keeps_claude_finished_after_token_metric(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Claude", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=30)
    metric_at = now - timedelta(seconds=10)
    metric_id = uuid4()
    window.agent_activity_latest_at = metric_at
    window.agent_activity_latest_event_id = metric_id
    window.agent_activity_latest_completed_at = completed_at
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json=claude_completion_payload(),
                fingerprint="claude-completed-before-token-metric",
                created_at=completed_at,
            ),
            Event(
                id=metric_id,
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="otel://claude-code/metrics",
                kind="otel_metric",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "claude_code",
                    "type": "otel_metric",
                    "name": "claude_code.token.usage",
                    "attributes": {"session.id": "claude-session-1"},
                    "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
                },
                fingerprint="claude-token-metric-after-completion",
                created_at=metric_at,
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    assert status.last_activity_at == completed_at
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at


@pytest.mark.asyncio
async def test_load_work_status_uses_cursor_assistant_message_as_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Cursor", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=20)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_event_id = uuid4()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="cursor-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json=cursor_completion_payload(),
            fingerprint="cursor-assistant-completed",
            created_at=completed_at,
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at

@pytest.mark.asyncio
async def test_load_work_status_uses_antigravity_final_model_response_as_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Antigravity", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=20)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_event_id = uuid4()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="antigravity-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json=antigravity_completion_payload(),
            fingerprint="antigravity-model-completed",
            created_at=completed_at,
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at
