from tests.unit.test_terminal_work_status_support import *

@pytest.mark.asyncio
async def test_postgres_load_work_status_uses_projected_user_input_without_scan(
    counted_db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_latest_at=now - timedelta(seconds=10),
        agent_activity_latest_user_input_at=now - timedelta(seconds=20),
    )
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex", "sequence": 9},
            fingerprint="postgres-projected-user-input-command",
            created_at=now - timedelta(seconds=30),
        )
    )
    await db_session.flush()

    async def latest_events_by_window(_session, _client_id, _window_ids, *, kind):
        if kind != "terminal_input_command":
            return {}
        return {
            window.id: Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex", "sequence": 9},
                fingerprint="postgres-projected-user-input-command-projected",
                created_at=now - timedelta(seconds=30),
            )
        }

    async def fail_user_input_scan(*_args, **_kwargs):
        raise AssertionError("projected Postgres user input should not scan recent agent events")

    monkeypatch.setattr("app.services.terminal_work_status._dialect_name", lambda _session: "postgresql")
    monkeypatch.setattr(
        "app.services.terminal_work_status._latest_events_by_window",
        latest_events_by_window,
    )
    monkeypatch.setattr(
        "app.services.terminal_work_status._latest_agent_user_input_at_by_window",
        fail_user_input_scan,
    )
    statements.clear()

    statuses = await load_work_statuses(db_session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "WORKING"
    assert not [
        statement
        for statement in statements
        if "FROM events" in statement and "events.source_type IN" in statement
    ]


@pytest.mark.asyncio
async def test_load_work_status_does_not_treat_latest_user_input_as_agent_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 20, tzinfo=timezone.utc)
    client_id = uuid4()
    input_at = now - timedelta(minutes=20)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Claude idle prompt",
        status=WindowStatus.active,
        agent_activity_latest_at=input_at,
        agent_activity_latest_user_input_at=input_at,
    )
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude --dangerously-skip-permissions", "sequence": 1},
            fingerprint="claude-command-user-input-only",
            created_at=input_at - timedelta(seconds=3),
        )
    )
    await db_session.flush()

    statuses = await load_work_statuses(db_session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "LONG_IDLE"


@pytest.mark.asyncio
async def test_load_work_status_keeps_pending_subagent_working_after_user_input(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 20, tzinfo=timezone.utc)
    client_id = uuid4()
    input_at = now - timedelta(minutes=20)
    window = VirtualWindow(
        id=uuid4(),
        client_id=client_id,
        title="Claude waiting for subagent",
        status=WindowStatus.active,
        agent_activity_latest_at=input_at,
        agent_activity_latest_user_input_at=input_at,
        agent_activity_pending_subagent_count=1,
    )
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "claude --dangerously-skip-permissions", "sequence": 1},
            fingerprint="claude-command-pending-subagent",
            created_at=input_at - timedelta(seconds=3),
        )
    )
    await db_session.flush()

    statuses = await load_work_statuses(db_session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "WORKING"


@pytest.mark.asyncio
async def test_finished_command_sequence_query_starts_at_latest_agent_command(counted_db_session) -> None:
    db_session, statements = counted_db_session
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.agent_activity_latest_at = now - timedelta(seconds=10)
    db_session.add_all(
        [
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_command_finished",
                virtual_window_id=window.id,
                payload_json={"sequence": 1},
                fingerprint="finished-before-latest-agent-command",
                created_at=now - timedelta(minutes=10),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window.id),
                kind="terminal_input_command",
                virtual_window_id=window.id,
                payload_json={"command": "codex exec 'fix'", "sequence": 2},
                fingerprint="latest-agent-command-for-finished-scope",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("working"),
                fingerprint="agent-output-after-latest-command",
                created_at=now - timedelta(seconds=10),
            ),
        ]
    )
    await db_session.flush()
    statements.clear()

    statuses = await load_work_statuses(db_session, client_id, [window.id], now=now)

    assert statuses[window.id].state == "WORKING"
    finished_queries = [
        statement
        for statement in statements
        if "FROM events" in statement and "events.kind = ?" in statement and "events.created_at >=" in statement
    ]
    assert len(finished_queries) == 1

@pytest.mark.asyncio
async def test_load_work_status_treats_agent_tool_record_output_as_working_activity(db_session) -> None:
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
                payload_json={"command": "codex", "sequence": 1},
                fingerprint="terminal-input-agent-record-work-status",
                created_at=now - timedelta(seconds=25),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="user_message",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "raw_type": "event_msg", "payload": {"type": "user_message", "message": "fix tests"}},
                fingerprint="agent-record-user-input-work-status",
                created_at=now - timedelta(seconds=22),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "raw_type": "event_msg", "payload": {"type": "agent_message", "message": "working"}},
                fingerprint="agent-record-output-work-status",
                created_at=now - timedelta(seconds=20),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"
    assert status.last_activity_at == now - timedelta(seconds=20)
    assert status.last_working_activity_at == now - timedelta(seconds=20)

@pytest.mark.asyncio
async def test_load_work_status_does_not_treat_empty_agent_launch_output_as_working(db_session) -> None:
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
                payload_json={"command": "codex", "sequence": 7},
                fingerprint="terminal-input-empty-codex",
                created_at=now - timedelta(seconds=30),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="session_meta",
                virtual_window_id=window.id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "session_meta",
                    "payload": {"id": "codex-session-1"},
                },
                fingerprint="codex-empty-launch-session-meta",
                created_at=now - timedelta(seconds=20),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_activity_at == now - timedelta(seconds=30)
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_treats_output_after_user_input_as_working(db_session) -> None:
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
                payload_json={"command": "codex", "sequence": 7},
                fingerprint="terminal-input-codex-user-start",
                created_at=now - timedelta(seconds=30),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_user_message_payload("fix tests"),
                fingerprint="codex-user-input-starts-work",
                created_at=now - timedelta(seconds=20),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="response_item",
                virtual_window_id=window.id,
                payload_json=codex_message_payload("working"),
                fingerprint="codex-output-after-user-input",
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
async def test_load_work_status_ignores_unprompted_agent_output_without_command(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-1",
            kind="response_item",
            virtual_window_id=window.id,
            payload_json=codex_message_payload("initial assistant output"),
            fingerprint="codex-unprompted-output-without-command",
            created_at=now - timedelta(seconds=10),
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "LONG_IDLE"
    assert status.last_activity_at is None
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_uses_lightweight_terminal_output_activity(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    window.terminal_last_output_at = now - timedelta(seconds=5)
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"

@pytest.mark.asyncio
async def test_load_work_status_keeps_agent_command_start_as_terminal_active_until_agent_output(db_session) -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window = VirtualWindow(id=uuid4(), client_id=client_id, title="Terminal", status=WindowStatus.active)
    db_session.add(window)
    await db_session.flush()
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window.id),
            kind="terminal_input_command",
            virtual_window_id=window.id,
            payload_json={"command": "codex exec 'fix tests'", "sequence": 7},
            fingerprint="terminal-input-codex",
            created_at=now - timedelta(seconds=30),
        )
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "RECENT_ACTIVE"
    assert status.last_working_activity_at is None

@pytest.mark.asyncio
async def test_load_work_status_keeps_agent_output_working_until_abort_threshold(
    db_session,
) -> None:
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
                payload_json={"command": "codex exec 'fix tests'", "sequence": 7},
                fingerprint="terminal-input-codex",
                created_at=now - timedelta(minutes=11),
            ),
            Event(
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id="codex-session-1",
                kind="assistant_message",
                virtual_window_id=window.id,
                payload_json={"provider": "codex", "role": "assistant", "content": "working"},
                fingerprint="codex-agent-stale-work-status",
                created_at=now - timedelta(minutes=11),
            ),
        ]
    )
    await db_session.flush()

    status = await load_work_status(db_session, client_id, window.id, now=now)

    assert status.state == "WORKING"
    assert status.last_activity_at == now - timedelta(seconds=30)
    assert status.last_working_activity_at == now - timedelta(seconds=30)
