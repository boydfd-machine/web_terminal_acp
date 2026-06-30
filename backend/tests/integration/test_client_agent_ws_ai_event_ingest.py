from tests.integration.test_client_agent_ws_support import *
from app.contexts.activity.application.agent_event_queue import AgentEventQueueConfig
def test_client_agent_websocket_persists_and_indexes_claude_ai_event(client_agent_db, monkeypatch):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    committed_before_index = False
    async def observe_commit(session):  # noqa: ANN001
        nonlocal committed_before_index
        committed_before_index = await _event_count(client_agent_db.session_factory) == 1
        await session.commit()
    monkeypatch.setattr(client_agent_router, "_commit_session", observe_commit)
    es_client = FakeElasticsearch(is_committed=lambda: committed_before_index)
    ui_event_hub = CaptureUiEventHub()
    monkeypatch.setattr(app.state, "es_client", es_client, raising=False)
    monkeypatch.setattr(app.state, "es_indexes_ready", True, raising=False)
    monkeypatch.setattr(
        client_agent_router,
        "_ui_event_hub",
        lambda _websocket: ui_event_hub,
    )
    event_payload = {
        "type": "assistant",
        "message": {"content": "managed hello"},
        "sessionId": "claude-managed-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
        "WEB_TERMINAL_PROJECT_PATH": "/workspace/claude-project",
    }
    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-claude-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/session.jsonl",
                            "offset": 11,
                            "payload": event_payload,
                        },
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()
    async def load_events():
        async with client_agent_db.session_factory() as session:
            rows = (await session.execute(select(Event))).scalars().all()
            ai_sessions = (await session.execute(select(AiSession))).scalars().all()
            return rows, ai_sessions
    rows, ai_sessions = asyncio.run(load_events())
    assert response == {
        "type": "ai_event_ack",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "request_id": "request-claude-1",
        "payload": {"ok": True},
    }
    assert len(rows) == 1
    assert rows[0].client_id == client_agent_db.client_id
    assert rows[0].virtual_window_id == window.id
    assert rows[0].source_type is EventSourceType.agent_tool_record
    assert rows[0].source_id == "claude-managed-session-1"
    assert rows[0].indexed_at is not None
    assert len(ai_sessions) == 1
    assert ai_sessions[0].provider == "claude_code"
    assert ai_sessions[0].source_id == "claude-managed-session-1"
    assert ai_sessions[0].source_path == "/home/user/.claude/session.jsonl"
    assert ai_sessions[0].project_path == "/workspace/claude-project"
    assert ai_sessions[0].virtual_window_id == window.id
    assert es_client.indexed_documents[0]["document"]["client_id"] == str(client_agent_db.client_id)
    assert es_client.indexed_documents[0]["document"]["virtual_window_id"] == str(window.id)
    assert es_client.indexed_documents[0]["document"]["provider"] == "claude_code"
    assert es_client.indexed_documents[0]["document"]["session_id"] == "claude-managed-session-1"
    assert ui_event_hub.invalidations == [
        {
            "resources": ["agent_record", "window", "search"],
            "client_id": client_agent_db.client_id,
            "window_id": window.id,
            "reason": "ai_event",
        }
    ]
def test_client_agent_websocket_persists_intermediate_codex_event_inline_when_queue_is_enabled(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    queued_events = []
    ui_event_hub = CaptureUiEventHub()

    async def capture_enqueue(event, *, redis_client=None, config=None):  # noqa: ANN001
        assert redis_client is not None
        queued_events.append((event, config))
        return "1-0"

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", capture_enqueue)
    monkeypatch.setattr(
        client_agent_router,
        "_ui_event_hub",
        lambda _websocket: ui_event_hub,
    )
    event_payload = {
        "trace_id": "trace-queued-1",
        "span": {"name": "tool_call", "attributes": {"tool": "bash"}},
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-queued-1",
                        payload={"provider": "codex", "payload": event_payload},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response == {
        "type": "ai_event_ack",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "request_id": "request-queued-1",
        "payload": {"ok": True},
    }
    assert len(queued_events) == 1
    queued_event, queued_config = queued_events[0]
    assert queued_config is config
    assert queued_event.client_id == client_agent_db.client_id
    assert queued_event.window_id == window.id
    assert queued_event.provider == "codex"
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 1
    assert ui_event_hub.invalidations == [
        {
            "resources": ["agent_record", "window", "search"],
            "client_id": client_agent_db.client_id,
            "window_id": window.id,
            "reason": "ai_event",
        }
    ]


def test_client_agent_websocket_persists_completion_ai_event_when_queue_is_enabled(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    queued_events = []
    ui_event_hub = CaptureUiEventHub()

    async def capture_enqueue(event, *, redis_client=None, config=None):  # noqa: ANN001
        assert redis_client is not None
        queued_events.append((event, config))
        return "1-0"

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", capture_enqueue)
    monkeypatch.setattr(
        client_agent_router,
        "_ui_event_hub",
        lambda _websocket: ui_event_hub,
    )
    event_payload = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": "done",
            "stop_reason": "end_turn",
        },
        "sessionId": "claude-completion-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
        "WEB_TERMINAL_PROJECT_PATH": "/workspace/claude-project",
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-completion-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/session.jsonl",
                            "offset": 99,
                            "payload": event_payload,
                        },
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response == {
        "type": "ai_event_ack",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "request_id": "request-completion-1",
        "payload": {"ok": True},
    }
    assert len(queued_events) == 1
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 1
    assert ui_event_hub.invalidations == [
        {
            "resources": ["agent_record", "window", "search", "project_todos"],
            "client_id": client_agent_db.client_id,
            "window_id": window.id,
            "reason": "ai_event",
        }
    ]


def test_client_agent_websocket_persists_intermediate_claude_event_inline_when_queue_is_enabled(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    queued_events = []
    ui_event_hub = CaptureUiEventHub()

    async def capture_enqueue(event, *, redis_client=None, config=None):  # noqa: ANN001
        assert redis_client is not None
        queued_events.append((event, config))
        return "1-0"

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", capture_enqueue)
    monkeypatch.setattr(
        client_agent_router,
        "_ui_event_hub",
        lambda _websocket: ui_event_hub,
    )
    event_payload = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": "working on it",
        },
        "sessionId": "claude-intermediate-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
        "WEB_TERMINAL_PROJECT_PATH": "/workspace/claude-project",
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-claude-intermediate-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/session.jsonl",
                            "offset": 42,
                            "payload": event_payload,
                        },
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response == {
        "type": "ai_event_ack",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "request_id": "request-claude-intermediate-1",
        "payload": {"ok": True},
    }
    assert len(queued_events) == 1
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 1
    assert ui_event_hub.invalidations == [
        {
            "resources": ["agent_record", "window", "search"],
            "client_id": client_agent_db.client_id,
            "window_id": window.id,
            "reason": "ai_event",
        }
    ]


def test_client_agent_websocket_does_not_inline_sidechain_completion_when_queue_is_enabled(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    queued_events = []

    async def capture_enqueue(event, *, redis_client=None, config=None):  # noqa: ANN001
        assert redis_client is not None
        queued_events.append((event, config))
        return "1-0"

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", capture_enqueue)
    event_payload = {
        "type": "assistant",
        "isSidechain": True,
        "agentId": "subagent-1",
        "message": {
            "role": "assistant",
            "content": "subagent done",
            "stop_reason": "end_turn",
        },
        "sessionId": "claude-sidechain-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-sidechain-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/subagents/agent-subagent-1.jsonl",
                            "offset": 99,
                            "payload": event_payload,
                        },
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response["payload"] == {"ok": True}
    assert len(queued_events) == 1
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 0


def test_client_agent_websocket_persists_claude_subagent_state_when_queue_is_enabled(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )
    queued_events = []

    async def capture_enqueue(event, *, redis_client=None, config=None):  # noqa: ANN001
        assert redis_client is not None
        queued_events.append((event, config))
        return "1-0"

    async def load_window_projection():
        async with client_agent_db.session_factory() as session:
            row = await session.scalar(select(VirtualWindow).where(VirtualWindow.id == window.id))
            return (
                row.agent_activity_pending_subagent_count,
                row.agent_activity_latest_completed_at,
                row.agent_activity_deferred_completed_at,
            )

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", capture_enqueue)
    subagent_call_payload = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "Agent",
                    "input": {
                        "description": "sleep",
                        "prompt": "run sleep 60",
                        "run_in_background": True,
                        "subagent_type": "general-purpose",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        "subagent_tool_use_results": [
            {
                "tool_use_id": "call-1",
                "agent_id": "subagent-1",
            }
        ],
        "sessionId": "claude-main-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
    }
    main_completion_payload = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": "waiting for subagent",
            "stop_reason": "end_turn",
        },
        "sessionId": "claude-main-session-1",
        "WEB_TERMINAL_CLIENT_ID": str(client_agent_db.client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-subagent-call-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/session.jsonl",
                            "offset": 10,
                            "payload": subagent_call_payload,
                        },
                    )
                )
            )
            assert websocket.receive_json()["payload"] == {"ok": True}
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-main-waiting-1",
                        payload={
                            "provider": "claude",
                            "source_path": "/home/user/.claude/session.jsonl",
                            "offset": 20,
                            "payload": main_completion_payload,
                        },
                    )
                )
            )
            assert websocket.receive_json()["payload"] == {"ok": True}
    finally:
        test_client.close()

    assert len(queued_events) == 2
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 2
    pending_count, latest_completed_at, deferred_completed_at = asyncio.run(load_window_projection())
    assert pending_count == 1
    assert latest_completed_at is None
    assert deferred_completed_at is not None


def test_client_agent_websocket_persists_ai_event_when_redis_queue_is_unavailable(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    config = AgentEventQueueConfig(
        redis_url="redis://redis:6379/0",
        stream_key="agent-events",
        dead_letter_stream_key="agent-events:dead-letter",
        consumer_group="agent-event-ingest",
        stream_maxlen=1000,
        worker_batch_size=10,
        block_ms=0,
        claim_idle_ms=1,
        max_deliveries=3,
        redis_timeout_seconds=0.1,
    )

    async def fail_enqueue(*_args, **_kwargs):
        raise client_agent_router.AgentEventQueueUnavailable("agent event queue is unavailable")

    monkeypatch.setattr(client_agent_router, "queue_config_from_settings", lambda: config)
    monkeypatch.setattr(client_agent_router, "enqueue_managed_agent_event", fail_enqueue)
    event_payload = {
        "trace_id": "trace-fallback-1",
        "span": {"name": "tool_call", "attributes": {"tool": "bash"}},
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-fallback-1",
                        payload={"provider": "codex", "payload": event_payload},
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    assert response == {
        "type": "ai_event_ack",
        "client_id": str(client_agent_db.client_id),
        "window_id": str(window.id),
        "request_id": "request-fallback-1",
        "payload": {"ok": True},
    }
    assert asyncio.run(_event_count(client_agent_db.session_factory)) == 1


def test_client_agent_websocket_persists_codex_ai_event(client_agent_db):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    event_payload = {
        "trace_id": "trace-managed-1",
        "span": {"name": "tool_call", "attributes": {"tool": "bash"}},
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
        "source_path": "/home/user/.codex/trace.jsonl",
        "project_path": "/workspace/codex-project-from-payload",
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-codex-1",
                        payload={
                            "provider": "codex",
                            "project_path": "/workspace/codex-project",
                            "payload": event_payload,
                        },
                    )
                )
            )
            response = websocket.receive_json()
    finally:
        test_client.close()

    async def load_events():
        async with client_agent_db.session_factory() as session:
            rows = (await session.execute(select(Event))).scalars().all()
            ai_sessions = (await session.execute(select(AiSession))).scalars().all()
            return rows, ai_sessions

    rows, ai_sessions = asyncio.run(load_events())
    assert response["type"] == "ai_event_ack"
    assert response["request_id"] == "request-codex-1"
    assert response["payload"] == {"ok": True}
    assert len(rows) == 1
    assert rows[0].client_id == client_agent_db.client_id
    assert rows[0].virtual_window_id == window.id
    assert rows[0].source_type is EventSourceType.agent_tool_record
    assert rows[0].source_id == "trace-managed-1"
    assert len(ai_sessions) == 1
    assert ai_sessions[0].provider == "codex"
    assert ai_sessions[0].source_id == "trace-managed-1"
    assert ai_sessions[0].source_path == "/home/user/.codex/trace.jsonl"
    assert ai_sessions[0].project_path == "/workspace/codex-project"
    assert ai_sessions[0].virtual_window_id == window.id

def test_client_agent_websocket_tracks_worktree_marker_from_codex_tool_output(
    client_agent_db,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    event_payload = {
        "trace_id": "trace-worktree-1",
        "name": "response_item",
        "type": "function_call_output",
        "output": f"Registered worktree\n{worktree_marker(window.id)}",
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-worktree-1",
                        payload={"provider": "codex", "payload": event_payload},
                    )
                )
            )
            response = websocket.receive_json()
            assert response["type"] == "ai_event_ack"
            assert response["payload"] == {"ok": True}
            wait_for_condition(
                lambda: asyncio.run(_worktree_binding_exists(client_agent_db.session_factory, window.id))
            )
    finally:
        test_client.close()

    async def load_state():
        async with client_agent_db.session_factory() as session:
            event = await session.scalar(
                select(Event).where(Event.virtual_window_id == window.id)
            )
            binding = await session.scalar(
                select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == window.id)
            )
            return event, binding

    event, binding = asyncio.run(load_state())
    assert event is not None
    assert event.source_type is EventSourceType.agent_tool_record
    assert binding is not None
    assert binding.worktree_root == "/repo/.worktrees/feature"
    assert binding.main_repo_root == "/repo"
    assert binding.discovery_method == "osc"

def test_client_agent_websocket_acks_worktree_ai_event_before_git_tracking(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    tracking_started = threading.Event()
    release_tracking = threading.Event()

    async def slow_process_worktree_registration(*args, **kwargs):
        tracking_started.set()
        await asyncio.to_thread(release_tracking.wait)

    monkeypatch.setattr(
        client_agent_router,
        "process_worktree_registration",
        slow_process_worktree_registration,
    )
    event_payload = {
        "trace_id": "trace-worktree-priority-1",
        "name": "response_item",
        "type": "function_call_output",
        "output": f"Registered worktree\n{worktree_marker(window.id)}",
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-worktree-priority-1",
                        payload={"provider": "codex", "payload": event_payload},
                    )
                )
            )
            response = websocket.receive_json()
            assert response["type"] == "ai_event_ack"
            assert response["payload"] == {"ok": True}
            assert asyncio.run(_event_count(client_agent_db.session_factory)) == 1
            wait_for_condition(tracking_started.is_set)
            release_tracking.set()
    finally:
        release_tracking.set()
        test_client.close()

def test_client_agent_websocket_refreshes_git_tracking_after_codex_tool_output(
    client_agent_db,
    monkeypatch,
):
    window = asyncio.run(create_remote_window(client_agent_db.session_factory, client_agent_db.client_id))
    asyncio.run(_set_client_runtime(client_agent_db.session_factory, client_agent_db.client_id, ClientRuntime.local))
    snapshots = [
        {
            "is_linked_worktree": True,
            "worktree_root": "/repo/.worktrees/feature",
            "main_repo_root": "/repo",
            "branch": "agent/feature",
            "head_sha": "base",
            "status_porcelain": "",
            "diff_stat": "",
            "staged_diff_stat": "",
            "commits": [],
        },
        {
            "is_linked_worktree": True,
            "worktree_root": "/repo/.worktrees/feature",
            "main_repo_root": "/repo",
            "branch": "agent/feature",
            "head_sha": "feature",
            "status_porcelain": "",
            "diff_stat": "",
            "staged_diff_stat": "",
            "commits": [
                {
                    "sha": "feature",
                    "short_sha": "feature",
                    "subject": "Fix terminal reload autofocus reconnect",
                    "author_name": "Open Claw",
                    "author_email": "open@example.com",
                    "authored_at": "2026-05-27T05:55:00+00:00",
                    "files": [
                        {
                            "path": "frontend/src/components/TerminalPane.tsx",
                            "old_path": None,
                            "status": "modified",
                            "additions": 12,
                            "deletions": 4,
                            "patch": "@@ -1 +1 @@\n-old\n+new\n",
                        }
                    ],
                }
            ],
        },
    ]

    async def fake_local_git_worktree_action(action: str, **payload):
        if action == "detect":
            return {
                "ok": True,
                "context": {
                    "is_linked_worktree": True,
                    "worktree_root": "/repo/.worktrees/feature",
                    "main_repo_root": "/repo",
                    "branch": "agent/feature",
                },
            }
        if action == "snapshot":
            snapshot = snapshots.pop(0) if len(snapshots) > 1 else snapshots[0]
            return {"ok": True, "snapshot": snapshot}
        return None

    monkeypatch.setattr(
        git_worktree_coordinator,
        "local_git_worktree_action",
        fake_local_git_worktree_action,
    )

    register_payload = {
        "trace_id": "trace-worktree-refresh-1",
        "name": "response_item",
        "type": "function_call_output",
        "output": f"Registered worktree\n{worktree_marker(window.id)}",
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }
    tool_payload = {
        "trace_id": "trace-worktree-refresh-1",
        "name": "response_item",
        "type": "function_call_output",
        "output": "git commit completed",
        "client_id": str(client_agent_db.client_id),
        "virtual_window_id": str(window.id),
    }

    test_client = TestClient(app)
    try:
        with connect_client_agent_bulk(test_client, client_agent_db) as websocket:
            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-worktree-register",
                        payload={"provider": "codex", "payload": register_payload},
                    )
                )
            )
            response = websocket.receive_json()
            assert response["type"] == "ai_event_ack"
            wait_for_condition(
                lambda: asyncio.run(_worktree_binding_exists(client_agent_db.session_factory, window.id))
            )

            websocket.send_text(
                encode_agent_message(
                    AgentMessage(
                        type="ai_event",
                        client_id=client_agent_db.client_id,
                        window_id=window.id,
                        request_id="request-worktree-refresh",
                        payload={"provider": "codex", "payload": tool_payload},
                    )
                )
            )
            response = websocket.receive_json()
            assert response["type"] == "ai_event_ack"
            assert response["payload"] == {"ok": True}
            wait_for_condition(
                lambda: asyncio.run(
                    _worktree_diff_contains_commit(client_agent_db.session_factory, window.id)
                )
            )
    finally:
        test_client.close()
