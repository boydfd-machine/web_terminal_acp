import json
from pathlib import Path
from uuid import uuid4

from app.client_agent.agent_tool_watchers.event_collectors import collect_cursor_watch_events
from app.client_agent.agent_tool_watchers.watch_state import AgentToolWatcherState
from app.client_agent.cursor_statusline import (
    STATUSLINE_USAGE_FILENAME,
    ensure_cursor_statusline_setup,
    statusline_payload_fingerprint,
)
from app.contexts.activity.application.agent_token_usage import (
    agent_token_usage_from_events,
    payload_is_token_usage_only,
    token_usage_from_payload,
)
from app.models import Event, EventSourceType


WINDOW_ID = uuid4()
CLIENT_ID = uuid4()


def test_token_usage_extracts_cursor_statusline_context_and_total() -> None:
    payload = {
        "provider": "cursor_cli",
        "type": "statusline_token_usage",
        "session_id": "cursor-session-1",
        "context_window": {
            "total_input_tokens": 15234,
            "total_output_tokens": 900,
            "context_window_size": 200000,
            "used_percentage": 7.6,
            "remaining_percentage": 92.4,
            "current_usage": {
                "inputTokens": 1200,
                "outputTokens": 45,
                "cacheReadTokens": 800,
                "cacheWriteTokens": 100,
            },
        },
    }

    snapshot = token_usage_from_payload(payload)

    assert snapshot is not None
    assert payload_is_token_usage_only(payload) is True
    assert snapshot.context is not None
    assert snapshot.context.total_tokens == 15234
    assert snapshot.context.cached_input_tokens == 0
    assert snapshot.total.cached_input_tokens == 800
    assert snapshot.total.cache_creation_input_tokens == 100
    assert snapshot.total.total_tokens == 16134
    assert snapshot.context_window == 200000


def test_agent_token_usage_aggregates_cursor_statusline_events() -> None:
    event = Event(
        client_id=CLIENT_ID,
        source_type=EventSourceType.agent_tool_record,
        source_id="cursor-session-1",
        kind="statusline_token_usage",
        virtual_window_id=WINDOW_ID,
        payload_json={
            "provider": "cursor_cli",
            "type": "statusline_token_usage",
            "session_id": "cursor-session-1",
            "context_window": {
                "total_input_tokens": 5000,
                "total_output_tokens": 250,
                "context_window_size": 200000,
            },
        },
        fingerprint="cursor-statusline-usage",
    )

    usage = agent_token_usage_from_events([event])

    assert usage is not None
    assert usage.context is not None
    assert usage.context.total_tokens == 5000
    assert usage.total.total_tokens == 5250
    assert usage.providers == ["cursor_cli"]
    assert usage.event_count == 1


def test_collect_cursor_watch_events_reads_statusline_usage(monkeypatch) -> None:
    home = Path.home()
    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID)
    cursor_home.mkdir(parents=True, exist_ok=True)
    usage_path = cursor_home / STATUSLINE_USAGE_FILENAME
    usage_path.write_text(
        json.dumps(
            {
                "session_id": "cursor-session-1",
                "context_window": {
                    "total_input_tokens": 3210,
                    "total_output_tokens": 120,
                    "context_window_size": 200000,
                },
            }
        ),
        encoding="utf-8",
    )

    state = AgentToolWatcherState()
    first = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )
    second = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path="/workspace/project",
    )

    assert len(first) == 1
    assert first[0].payload["type"] == "statusline_token_usage"
    assert first[0].payload["context_window"]["total_input_tokens"] == 3210
    assert second == []


def test_collect_cursor_watch_events_emits_when_statusline_usage_changes() -> None:
    home = Path.home()
    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID)
    cursor_home.mkdir(parents=True, exist_ok=True)
    usage_path = cursor_home / STATUSLINE_USAGE_FILENAME

    state = AgentToolWatcherState()
    usage_path.write_text(
        json.dumps({"session_id": "cursor-session-1", "context_window": {"total_input_tokens": 100}}),
        encoding="utf-8",
    )
    first = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path=None,
    )
    usage_path.write_text(
        json.dumps({"session_id": "cursor-session-1", "context_window": {"total_input_tokens": 200}}),
        encoding="utf-8",
    )
    second = collect_cursor_watch_events(
        state,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        project_path=None,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].payload["context_window"]["total_input_tokens"] == 100
    assert second[0].payload["context_window"]["total_input_tokens"] == 200


def test_ensure_cursor_statusline_setup_materializes_config_and_installs_writer() -> None:
    home = Path.home()
    source_cursor = home / ".cursor"
    source_cursor.mkdir(parents=True, exist_ok=True)
    source_config = source_cursor / "cli-config.json"
    source_config.write_text('{"version": 1, "model": {"modelId": "composer-2.5"}}\n', encoding="utf-8")

    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / str(WINDOW_ID)
    cursor_home.mkdir(parents=True, exist_ok=True)
    managed_config = cursor_home / "cli-config.json"
    managed_config.symlink_to(source_config)

    ensure_cursor_statusline_setup(WINDOW_ID)

    writer = cursor_home / "bin" / "cursor-statusline-writer.sh"
    assert writer.is_file()
    assert writer.stat().st_mode & 0o111
    assert not managed_config.is_symlink()
    config = json.loads(managed_config.read_text(encoding="utf-8"))
    assert config["statusLine"]["command"] == str(writer)
    assert config["statusLine"]["updateIntervalMs"] == 500


def test_statusline_payload_fingerprint_is_stable() -> None:
    payload = {"session_id": "abc", "context_window": {"total_input_tokens": 1}}
    assert statusline_payload_fingerprint(payload) == statusline_payload_fingerprint(payload)
