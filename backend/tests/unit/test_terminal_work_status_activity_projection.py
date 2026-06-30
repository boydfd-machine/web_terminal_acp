from tests.unit.test_terminal_work_status_support import *

def test_work_status_from_activity_returns_long_idle_after_recent_window() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=11),
        last_working_activity_at=now - timedelta(minutes=11),
    )

    assert status.state == "LONG_IDLE"
    assert status.label == "长时间没有工作了"
    assert status.color == "gray"

def test_work_status_from_activity_prefers_working_for_recent_agent_activity() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(seconds=20),
        last_agent_active_at=now - timedelta(seconds=25),
        last_agent_output_at=now - timedelta(seconds=20),
    )

    assert status.state == "WORKING"
    assert status.label == "Agent 工作中"
    assert status.color == "orange"

def test_work_status_from_activity_returns_recent_active_for_stale_unmanaged_agent_activity() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=2),
        last_working_activity_at=now - timedelta(minutes=2),
    )

    assert status.state == "RECENT_ACTIVE"

def test_work_status_from_activity_returns_recent_active_for_recent_input_only() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=2),
        last_working_activity_at=None,
    )

    assert status.state == "RECENT_ACTIVE"
    assert status.label == "Terminal 活跃"
    assert status.color == "green"

def test_work_status_from_activity_does_not_treat_output_before_terminal_activity_as_active_agent() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(seconds=20),
        last_terminal_activity_at=now - timedelta(seconds=20),
        last_agent_output_at=now - timedelta(seconds=30),
    )

    assert status.state == "RECENT_ACTIVE"
    assert status.label == "Terminal 活跃"

def test_work_status_from_activity_returns_finished_for_recent_explicit_completion() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(seconds=20),
        last_agent_active_at=now - timedelta(minutes=2),
        last_agent_output_at=now - timedelta(seconds=30),
        last_agent_completed_at=now - timedelta(seconds=20),
    )

    assert status.state == "FINISHED"
    assert status.label == "Agent 已完成"
    assert status.color == "green"

def test_work_status_from_activity_returns_working_when_output_follows_completion() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(seconds=10),
        last_agent_active_at=now - timedelta(seconds=10),
        last_agent_output_at=now - timedelta(seconds=10),
        last_agent_completed_at=now - timedelta(seconds=30),
    )

    assert status.state == "WORKING"

def test_work_status_from_activity_returns_aborted_for_agent_without_output_over_one_hour() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=61),
        last_agent_active_at=now - timedelta(minutes=70),
        last_agent_output_at=now - timedelta(minutes=61),
    )

    assert status.state == "ABORTED"
    assert status.label == "Agent 可能已中断"
    assert status.color == "red"

def test_work_status_from_activity_returns_aborted_for_agent_command_with_no_output_over_one_hour() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=70),
        last_agent_active_at=now - timedelta(minutes=70),
        last_agent_output_at=None,
    )

    assert status.state == "ABORTED"
    assert status.label == "Agent 可能已中断"
    assert status.color == "red"

def test_work_status_from_activity_returns_sleeping_after_abort_notice_window() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    status = work_status_from_activity(
        now=now,
        last_activity_at=now - timedelta(minutes=75),
        last_agent_active_at=now - timedelta(minutes=90),
        last_agent_output_at=now - timedelta(minutes=75),
    )

    assert status.state == "LONG_IDLE"

@pytest.mark.asyncio
async def test_load_work_statuses_batches_latest_activity_queries(counted_db_session) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    windows = [
        VirtualWindow(id=uuid4(), client_id=client_id, title=f"Terminal {index}", status=WindowStatus.active)
        for index in range(3)
    ]
    db_session.add_all(windows)
    await db_session.flush()
    windows[0].terminal_last_output_at = now - timedelta(seconds=15)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(windows[1].id),
                kind="terminal_input_command",
                virtual_window_id=windows[1].id,
                payload_json={"command": "codex exec 'fix'", "sequence": 1},
                fingerprint="terminal-input-agent-tool-record-latest",
                created_at=now - timedelta(seconds=12),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="assistant_message",
                virtual_window_id=windows[1].id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint="agent-tool-record-latest",
                created_at=now - timedelta(seconds=10),
            ),
        ]
    )
    await db_session.flush()
    statements.clear()

    statuses = await load_work_statuses(
        db_session,
        client_id,
        [window.id for window in windows],
        now=now,
    )

    assert statuses[windows[0].id].state == "RECENT_ACTIVE"
    assert statuses[windows[1].id].state == "WORKING"
    latest_activity_queries = [
        statement
        for statement in statements
        if "events.created_at" in statement
        and "virtual_windows" in statement
        and "SELECT virtual_windows.id" in statement
    ]
    assert len(latest_activity_queries) <= 2

@pytest.mark.asyncio
async def test_load_work_statuses_uses_bounded_agent_event_queries(counted_db_session) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    windows = [
        VirtualWindow(id=uuid4(), client_id=client_id, title=f"Terminal {index}", status=WindowStatus.active)
        for index in range(2)
    ]
    db_session.add_all(windows)
    await db_session.flush()
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(windows[0].id),
                kind="terminal_input_command",
                virtual_window_id=windows[0].id,
                payload_json={"command": "codex exec 'fix'", "sequence": 1},
                fingerprint="bounded-agent-query-command",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=windows[0].id,
                payload_json=codex_message_payload("working"),
                fingerprint="bounded-agent-query-output",
                created_at=now - timedelta(seconds=10),
            ),
        ]
    )
    await db_session.flush()
    statements.clear()

    statuses = await load_work_statuses(
        db_session,
        client_id,
        [window.id for window in windows],
        now=now,
    )

    assert statuses[windows[0].id].state == "WORKING"
    agent_event_queries = [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]
    assert len(agent_event_queries) == 1
    assert all("'agent_tool_record'" in statement for statement in agent_event_queries)
    assert all("'codex_trace'" in statement for statement in agent_event_queries)
    assert all("'claude_jsonl'" in statement for statement in agent_event_queries)
    assert all("row_number" in statement.lower() for statement in agent_event_queries)
    assert all("partition by" in statement.lower() for statement in agent_event_queries)

@pytest.mark.asyncio
async def test_load_work_statuses_uses_window_agent_activity_state(counted_db_session) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_latest_at=now - timedelta(seconds=10),
    )
    db_session.add(window)
    await db_session.flush()
    statements.clear()

    statuses = await load_work_statuses(db_session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "LONG_IDLE"
    agent_event_queries = [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]
    assert len(agent_event_queries) == 1
    assert "row_number" in agent_event_queries[0].lower()
    assert "partition by" in agent_event_queries[0].lower()

@pytest.mark.asyncio
async def test_postgres_activity_projection_does_not_scan_empty_agent_windows(
    counted_db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session, statements = counted_db_session
    client_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
    )
    db_session.add(window)
    await db_session.flush()
    monkeypatch.setattr("app.services.terminal_work_status._dialect_name", lambda _session: "postgresql")
    statements.clear()

    activity = await terminal_work_status._agent_activity_state_by_window(
        db_session,
        client_id,
        [window.id],
    )

    assert window.id not in activity.latest_activity
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]

@pytest.mark.asyncio
async def test_postgres_activity_projection_repairs_stale_latest_event_without_scan(
    counted_db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    completed_at = now - timedelta(minutes=2)
    local_command_at = now - timedelta(seconds=10)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_latest_at=local_command_at,
        agent_activity_latest_completed_at=completed_at,
    )
    local_command = Event(
        id=uuid4(),
        client_id=client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="claude-session-1",
        kind="user_message",
        virtual_window_id=window.id,
        payload_json=claude_local_command_payload(),
        fingerprint="claude-local-command-after-finish-projection",
        created_at=local_command_at,
    )
    window.agent_activity_latest_event_id = local_command.id
    db_session.add_all([window, local_command])
    await db_session.flush()
    monkeypatch.setattr("app.services.terminal_work_status._dialect_name", lambda _session: "postgresql")
    statements.clear()

    activity = await terminal_work_status._agent_activity_state_by_window(
        db_session,
        client_id,
        [window.id],
    )

    assert activity.latest_activity[window.id] == completed_at
    assert activity.latest_completed_at[window.id] == completed_at
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]

@pytest.mark.asyncio
async def test_postgres_activity_projection_repairs_empty_agent_launch_event_without_scan(
    counted_db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    latest_at = now - timedelta(seconds=10)
    session_meta = Event(
        id=uuid4(),
        client_id=client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="session_meta",
        virtual_window_id=None,
        payload_json={
            "provider": "codex",
            "raw_type": "session_meta",
            "payload": {"id": "codex-session-1"},
        },
        fingerprint="codex-empty-launch-projection",
        created_at=latest_at,
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_latest_at=latest_at,
        agent_activity_latest_event_id=session_meta.id,
    )
    session_meta.virtual_window_id = window.id
    db_session.add_all([window, session_meta])
    await db_session.flush()
    monkeypatch.setattr("app.services.terminal_work_status._dialect_name", lambda _session: "postgresql")
    statements.clear()

    activity = await terminal_work_status._agent_activity_state_by_window(
        db_session,
        client_id,
        [window.id],
    )

    assert window.id not in activity.latest_activity
    assert window.id not in activity.latest_completed_at
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]

@pytest.mark.asyncio
async def test_postgres_activity_projection_repairs_latest_failure_without_scan(
    counted_db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    failed_at = now - timedelta(seconds=10)
    failure_event = Event(
        id=uuid4(),
        client_id=client_id,
        source_type=EventSourceType.agent_tool_record,
        source_id="codex-session-1",
        kind="event_msg",
        virtual_window_id=None,
        payload_json={
            "provider": "codex",
            "raw_type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "stream disconnected before completion: stream closed before response.completed",
            },
        },
        fingerprint="codex-stream-disconnect-projection",
        created_at=failed_at,
    )
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_latest_at=failed_at,
        agent_activity_latest_event_id=failure_event.id,
    )
    failure_event.virtual_window_id = window.id
    db_session.add_all([window, failure_event])
    await db_session.flush()
    monkeypatch.setattr("app.services.terminal_work_status._dialect_name", lambda _session: "postgresql")
    statements.clear()

    activity = await terminal_work_status._agent_activity_state_by_window(
        db_session,
        client_id,
        [window.id],
    )

    assert activity.latest_activity[window.id] == failed_at
    assert activity.latest_failed_at[window.id] == failed_at
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]
