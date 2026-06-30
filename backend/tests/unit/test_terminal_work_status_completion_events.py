from tests.unit.test_terminal_work_status_support import *

@pytest.mark.asyncio
async def test_load_work_status_stops_agent_activity_after_shell_exit_without_completion(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(seconds=30)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "claude", "sequence": 8},
                fingerprint="terminal-input-claude-exit-without-completion",
                created_at=now - timedelta(seconds=40),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={"provider": "claude_code", "role": "assistant", "content": "working"},
                fingerprint="claude-agent-output-before-exit",
                created_at=now - timedelta(seconds=30),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 8, "exit_status": 0},
                fingerprint="terminal-finished-claude-exit-without-completion",
                created_at=now - timedelta(seconds=20),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_activity_at == now - timedelta(seconds=20)
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_allows_recent_late_agent_output_after_shell_exit(db_session) -> None:
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
                payload_json={"command": "codex exec 'done'", "sequence": 9},
                fingerprint="terminal-input-codex-late-agent-output",
                created_at=now - timedelta(seconds=40),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 9, "exit_status": 0},
                fingerprint="terminal-finished-codex-late-agent-output",
                created_at=now - timedelta(seconds=20),
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
                        "content": [{"type": "output_text", "text": "late watcher write"}],
                    },
                },
                fingerprint="codex-agent-output-after-shell-exit",
                created_at=now - timedelta(seconds=5),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"
    assert status.last_activity_at == now - timedelta(seconds=5)
    assert status.last_working_activity_at == now - timedelta(seconds=5)

@pytest.mark.asyncio
async def test_load_work_status_ignores_late_agent_output_after_shell_exit_delay_window(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(seconds=40)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'done'", "sequence": 10},
                fingerprint="terminal-input-codex-late-agent-output-delay",
                created_at=now - timedelta(seconds=80),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 10, "exit_status": 0},
                fingerprint="terminal-finished-codex-late-agent-output-delay",
                created_at=now - timedelta(seconds=60),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("late watcher write"),
                fingerprint="codex-agent-output-after-shell-exit-delay",
                created_at=now - timedelta(seconds=5),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_activity_at == now - timedelta(seconds=60)
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_ignores_old_agent_output_written_after_shell_exit(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'done'", "sequence": 12},
                fingerprint="terminal-input-codex-old-output-late-write",
                created_at=now - timedelta(seconds=80),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"command": "", "sequence": 12, "exit_status": 0},
                fingerprint="terminal-finished-codex-old-output-late-write",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload(
                    "old output inserted late",
                    timestamp=now - timedelta(seconds=40),
                ),
                fingerprint="codex-agent-old-output-late-write",
                created_at=now - timedelta(seconds=5),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_activity_at == now - timedelta(seconds=20)
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_returns_to_working_after_completion_in_same_running_session(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex", "sequence": 11},
                fingerprint="terminal-input-codex-multi-turn",
                created_at=now - timedelta(minutes=3),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_user_message_payload("first turn"),
                fingerprint="codex-agent-first-turn-user-input",
                created_at=now - timedelta(seconds=50),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json=codex_completion_payload(),
                fingerprint="codex-agent-first-turn-complete",
                created_at=now - timedelta(seconds=40),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("second turn started"),
                fingerprint="codex-agent-second-turn-output",
                created_at=now - timedelta(seconds=10),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"
    assert status.last_activity_at == now - timedelta(seconds=10)
    assert status.last_working_activity_at == now - timedelta(seconds=10)

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_uses_codex_completion_event(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    started_at = now - timedelta(seconds=30)
    completed_at = now - timedelta(seconds=5)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_completed_at = completed_at
    db_session.add_all([
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'done'", "sequence": 2},
            fingerprint="terminal-input-codex",
            created_at=started_at,
        ),
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="event_msg",
            virtual_window_id=window.id,
            payload_json=codex_completion_payload(),
            fingerprint="codex-agent-completed",
            created_at=completed_at,
        ),
    ])
    await db_session.flush()

    latest = await load_last_agent_task_completed_at_by_window(db_session, client_id, [window.id])

    stored = latest[window.id]
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == completed_at

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_uses_codex_task_complete_event(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=5)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_completed_at = completed_at
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("done", timestamp=completed_at - timedelta(seconds=1)),
                fingerprint="codex-agent-final-message-before-task-complete",
                created_at=completed_at - timedelta(seconds=1),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="event_msg",
                virtual_window_id=window.id,
                payload_json=codex_completion_payload(event_type="task_complete", timestamp=completed_at),
                fingerprint="codex-agent-task-complete",
                created_at=completed_at,
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    assert latest[window.id] == completed_at
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at

@pytest.mark.asyncio
async def test_load_last_agent_task_completed_uses_claude_turn_duration_event(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    completed_at = now - timedelta(seconds=5)
    window.agent_activity_latest_at = completed_at
    window.agent_activity_latest_completed_at = completed_at
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session-1",
            kind="system",
            virtual_window_id=window.id,
            payload_json=claude_turn_duration_payload(timestamp=completed_at),
            fingerprint="claude-agent-turn-duration-complete",
            created_at=completed_at,
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)
    latest = await load_last_agent_task_completed_at_by_window(
        db_session,
        client_id,
        [window.id],
        now=now,
    )
    activity = await load_tree_window_activity(db_session, client_id, [window.id], now=now)

    assert status.state == "FINISHED"
    assert latest[window.id] == completed_at
    task_status = activity.last_agent_task_status[window.id]
    assert task_status.state == "FINISHED"
    assert task_status.occurred_at == completed_at
