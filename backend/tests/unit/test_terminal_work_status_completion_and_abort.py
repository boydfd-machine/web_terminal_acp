from tests.unit.test_terminal_work_status_support import *

@pytest.mark.asyncio
async def test_claude_local_command_events_do_not_override_turn_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(minutes=2)
    local_command_at = now - timedelta(seconds=10)
    window.agent_activity_latest_at = local_command_at
    window.agent_activity_latest_completed_at = completed_at
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="system",
                virtual_window_id=window.id,
                payload_json=claude_turn_duration_payload(timestamp=completed_at),
                fingerprint="claude-agent-turn-duration-before-local-command",
                created_at=completed_at,
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="user_message",
                virtual_window_id=window.id,
                payload_json=claude_local_command_payload("<bash-stdout>WEB_TERMINAL_CLAUDE_CODE_HOME=...</bash-stdout>"),
                fingerprint="claude-local-command-after-finish",
                created_at=local_command_at,
            ),
        ]
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "FINISHED"
    assert activity.work_statuses[window.id].last_working_activity_at is None
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_ignores_agent_output_without_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    result_at = now - timedelta(seconds=10)
    window.agent_activity_latest_at = result_at
    db_session.add(
        Event(
            client_id=client_id,
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
                    "content": [{"type": "output_text", "text": "still working"}],
                },
            },
            fingerprint="codex-agent-result-still-working",
            created_at=result_at,
        )
    )
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    assert latest == {}

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_ignores_agent_command_without_result_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=30)
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'done'", "sequence": 2},
            fingerprint="terminal-input-codex",
            created_at=completed_at - timedelta(seconds=5),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2},
            fingerprint="terminal-finished-codex",
            created_at=completed_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    assert latest == {}

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_does_not_treat_shell_exit_as_agent_completion(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    old_completed_at = now - timedelta(minutes=10)
    new_started_at = now - timedelta(minutes=2)
    new_finished_at = now - timedelta(minutes=1)
    window.agent_activity_latest_at = old_completed_at
    window.agent_activity_latest_completed_at = old_completed_at
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude -p 'fix'", "sequence": 1},
            fingerprint="terminal-input-claude-old",
            created_at=old_completed_at - timedelta(seconds=10),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json=claude_completion_payload(),
            fingerprint="claude-agent-completed-old",
            created_at=old_completed_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude", "sequence": 2},
            fingerprint="terminal-input-claude-new",
            created_at=new_started_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_command_finished",
            virtual_window_id=window.id,
            payload_json={"command": "", "sequence": 2, "exit_status": 0},
            fingerprint="terminal-finished-claude-new",
            created_at=new_finished_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == old_completed_at

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_prefers_newer_completion_event(
    db_session,
) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    older_completed_at = now - timedelta(minutes=2)
    newer_completed_at = now - timedelta(seconds=5)
    window.agent_activity_latest_at = newer_completed_at
    window.agent_activity_latest_completed_at = newer_completed_at
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'newer done'", "sequence": 2},
            fingerprint="terminal-input-codex-newer",
            created_at=newer_completed_at - timedelta(seconds=30),
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json=claude_completion_payload(),
            fingerprint="claude-agent-completed-older",
            created_at=older_completed_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="event_msg",
            virtual_window_id=window.id,
            payload_json=codex_completion_payload(),
            fingerprint="codex-agent-completed-newer",
            created_at=newer_completed_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == newer_completed_at

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_ignores_idle_agent_activity_without_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    working_at = now - timedelta(seconds=120)
    window.agent_activity_latest_at = working_at
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={"provider": "claude_code", "role": "assistant", "content": "working"},
            fingerprint="claude-agent-idle-work",
            created_at=working_at,
        )
    )
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )

    assert latest == {}

@pytest.mark.asyncio
async def test_load_tree_window_activity_reports_abort_notification_status(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    output_at = now - timedelta(minutes=61)
    window.agent_activity_latest_at = output_at
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'hang'", "sequence": 2},
            fingerprint="terminal-input-codex-hang",
            created_at=now - timedelta(minutes=62),
        ),
        Event(
            client_id=client_id,
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
                    "content": [{"type": "output_text", "text": "still running"}],
                },
            },
            fingerprint="codex-agent-hang-output",
            created_at=output_at,
        ),
    ])
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "ABORTED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "ABORTED"
    assert task_status.occurred_at == output_at + timedelta(hours=1)

@pytest.mark.asyncio
async def test_load_tree_window_activity_reports_abort_for_agent_command_with_no_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    command_at = now - timedelta(minutes=70)
    window.agent_activity_latest_at = command_at
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'hang before output'", "sequence": 2},
            fingerprint="terminal-input-codex-no-output-hang",
            created_at=command_at,
        )
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "ABORTED"
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "ABORTED"
    assert task_status.occurred_at == command_at + timedelta(hours=1)

@pytest.mark.asyncio
async def test_load_tree_window_activity_does_not_abort_after_shell_exit_without_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(minutes=71)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'exit without semantic completion'", "sequence": 2},
                fingerprint="terminal-input-codex-exit-no-completion",
                created_at=now - timedelta(minutes=72),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("ran but no completion event"),
                fingerprint="codex-agent-output-exit-no-completion",
                created_at=now - timedelta(minutes=71),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 2, "exit_status": 0},
                fingerprint="terminal-finished-codex-exit-no-completion",
                created_at=now - timedelta(minutes=70),
            ),
        ]
    )
    await db_session.flush()

    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert activity.work_statuses[window.id].state == "LONG_IDLE"
    assert window.id not in activity.last_agent_task_status
