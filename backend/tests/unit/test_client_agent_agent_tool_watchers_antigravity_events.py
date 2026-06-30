from tests.unit.test_client_agent_agent_tool_watchers_support import *

def test_collect_cursor_watch_events_discovers_additional_store_after_first_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    first_store = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "state-a" / "store.db"
    first_store.parent.mkdir(parents=True)
    write_cursor_store(first_store)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    first = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    second_store = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID) / "state-b" / "store.db"
    second_store.parent.mkdir(parents=True)
    write_cursor_store(second_store)
    second = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.source_path for event in first] == [str(first_store), str(first_store)]
    assert second == []
    assert state.cursor_store_paths == [first_store, second_store]

    append_cursor_blob(second_store, "new-assistant-blob", "assistant", "new cursor")
    third = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert [event.source_path for event in third] == [str(second_store)]
    assert [event.payload["blob_id"] for event in third] == ["new-assistant-blob"]

def test_collect_antigravity_watch_events_reads_managed_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    session_id = "antigravity-session-1"
    transcript = (
        home
        / ".web-terminal-acp"
        / "antigravity-cli-homes"
        / str(WINDOW_ID)
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "content": "done",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)
    bootstrapped = watchers.collect_antigravity_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(bootstrapped) == 1
    assert bootstrapped[0].payload["content"] == "done"

    offset = transcript.stat().st_size
    transcript.write_text(
        transcript.read_text(encoding="utf-8")
        + json.dumps(
            {
                "step_index": 2,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "status": "DONE",
                "content": "fix tests",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events = watchers.collect_antigravity_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(events) == 1
    event = events[0]
    assert event.provider == "antigravity_cli"
    assert event.source_path == str(transcript)
    assert event.offset == offset
    assert event.cursor == offset
    assert event.project_path == "/workspace/project"
    assert event.payload["session_id"] == session_id
    assert event.payload["WEB_TERMINAL_CLIENT_ID"] == str(CLIENT_ID)
    assert event.payload["WEB_TERMINAL_WINDOW_ID"] == str(WINDOW_ID)
    assert event.payload["WEB_TERMINAL_PROJECT_PATH"] == "/workspace/project"

@pytest.mark.asyncio
async def test_enqueue_managed_ai_event_includes_cursor_and_project_path() -> None:
    from app.client_agent.ai_events import ManagedAiEvent

    messages: list[AgentMessage] = []

    async def send_message(message: AgentMessage) -> None:
        messages.append(message)

    payload = {
        "client_id": str(CLIENT_ID),
        "virtual_window_id": str(WINDOW_ID),
        "agentId": "cursor-agent-1",
        "blob_id": "assistant-blob",
        "role": "assistant",
        "text": "hello",
    }
    event = ManagedAiEvent(
        provider="cursor_cli",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        source_path="/tmp/store.db",
        offset=None,
        cursor="root-1",
        project_path="/workspace/project",
        payload=payload,
    )

    sent = await enqueue_managed_ai_event(send_message, event)

    assert sent is True
    assert len(messages) == 1
    message = messages[0]
    assert message.type == "ai_event"
    assert message.client_id == CLIENT_ID
    assert message.window_id == WINDOW_ID
    assert message.payload == {
        "provider": "cursor_cli",
        "source_path": "/tmp/store.db",
        "offset": None,
        "cursor": "root-1",
        "project_path": "/workspace/project",
        "payload": payload,
    }

def test_collect_antigravity_watch_events_with_subagent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    main_session_id = "main-session-1"
    sub_session_id = "subagent-1"

    # 1. Create main session transcript
    main_transcript = (
        home
        / ".web-terminal-acp"
        / "antigravity-cli-homes"
        / str(WINDOW_ID)
        / "brain"
        / main_session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    main_transcript.parent.mkdir(parents=True)

    # Tool call to invoke_subagent
    step_2 = {
        "step_index": 2,
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "status": "DONE",
        "tool_calls": [
            {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": '[{"Prompt": "Return exactly: 1", "Role": "Greeter Agent", "TypeName": "self"}]'
                }
            }
        ]
    }

    # Tool result INVOKE_SUBAGENT
    step_3 = {
        "step_index": 3,
        "source": "MODEL",
        "type": "INVOKE_SUBAGENT",
        "status": "DONE",
        "content": f'Created the following subagents:\n{{\n  "conversationId": "{sub_session_id}",\n  "workspaceUris": []\n}}',
    }

    step_4 = {
        "step_index": 4,
        "source": "SYSTEM",
        "type": "SYSTEM_MESSAGE",
        "status": "DONE",
        "content": (
            "The following is a <SYSTEM_MESSAGE> not actually sent by the user.\n\n"
            "<SYSTEM_MESSAGE>\n"
            f"[Message] timestamp=2026-06-02T05:52:12Z sender={sub_session_id} "
            "priority=MESSAGE_PRIORITY_HIGH content=1\n"
            "</SYSTEM_MESSAGE>"
        ),
    }

    main_transcript.write_text(
        json.dumps(step_2) + "\n" + json.dumps(step_3) + "\n" + json.dumps(step_4) + "\n",
        encoding="utf-8",
    )

    # 2. Create subagent session transcript
    sub_transcript = (
        home
        / ".web-terminal-acp"
        / "antigravity-cli-homes"
        / str(WINDOW_ID)
        / "brain"
        / sub_session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    sub_transcript.parent.mkdir(parents=True)

    sub_step_1 = {
        "step_index": 1,
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "status": "DONE",
        "content": "Return exactly: 1",
    }

    sub_transcript.write_text(
        json.dumps(sub_step_1) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "home", lambda: home)
    state = AgentToolWatcherState()

    initialize_agent_tool_watcher_state(state, window_id=WINDOW_ID)
    state.antigravity_offsets[main_transcript] = 0
    state.antigravity_offsets[sub_transcript] = 0
    bootstrapped = watchers.collect_antigravity_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    # Check that events from both main session and sub session were collected
    assert len(bootstrapped) == 4

    # Group events by source_path/session_id
    main_events = sorted([e for e in bootstrapped if "main-session-1" in e.source_path and "subagents" not in e.source_path], key=lambda x: x.payload["step_index"])
    sub_events = [e for e in bootstrapped if "subagents" in e.source_path]

    assert len(main_events) == 3
    assert len(sub_events) == 1

    # Check tool call matches got attached to main_events[0] (step 2)
    assert main_events[0].payload["subagent_tool_use_results"] == [
        {"tool_use_id": "step-2", "agent_id": sub_session_id}
    ]

    # Check tool use result got attached to main_events[1] (step 3)
    assert main_events[1].payload["toolUseResult"] == {
        "agentId": sub_session_id,
        "toolUseId": "step-2",
    }
    assert main_events[2].payload["toolUseResult"] == {
        "agentId": sub_session_id,
        "toolUseId": "step-2",
    }

    # Check subagent metadata got attached to sub_events[0]
    payload = sub_events[0].payload
    assert sub_events[0].source_path == f"/tmp/{main_session_id}/subagents/agent-{sub_session_id}.jsonl"
    assert payload["session_id"] == f"agent-{sub_session_id}"
    assert payload["isSidechain"] is True
    assert payload["agentId"] == sub_session_id
    assert payload["sessionId"] == main_session_id
    assert payload["subagent"] == {
        "toolUseId": "step-2",
        "tool_use_id": "step-2",
        "agentId": sub_session_id,
        "agent_id": sub_session_id,
    }
