import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import app.client_agent.codex_watcher as codex_watcher
from app.client_agent.codex_watcher import iter_recent_codex_session_files, read_new_codex_events


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")


def test_read_new_codex_events_attributes_session_lines_to_window(tmp_path) -> None:
    session_path = tmp_path / "rollout-2026-05-21T00-00-00-session-1.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-21T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-1", "cwd": "/tmp"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-05-21T00:00:01Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    assert next_offset == session_path.stat().st_size
    assert len(events) == 2
    payload, line_offset = events[0]
    assert line_offset == 0
    assert payload["trace_id"] == "session-1"
    assert payload["id"] == "session-1:0"
    assert payload["name"] == "session_meta"
    assert payload["client_id"] == str(CLIENT_ID)
    assert payload["virtual_window_id"] == str(WINDOW_ID)
    assert payload["source_path"] == str(session_path)
    usage_payload, usage_line_offset = events[1]
    assert usage_line_offset > line_offset
    assert usage_payload["name"] == "event_msg"
    assert usage_payload["payload"]["type"] == "token_count"


def test_read_new_codex_events_keeps_token_count_usage_events(tmp_path) -> None:
    session_path = tmp_path / "rollout-session-token-count.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-21T00:00:01Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
                        "last_token_usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    assert next_offset == session_path.stat().st_size
    assert len(events) == 1
    payload, _line_offset = events[0]
    assert payload["name"] == "event_msg"
    assert payload["payload"]["type"] == "token_count"
    assert payload["virtual_window_id"] == str(WINDOW_ID)


def test_read_new_codex_events_keeps_turn_context_events(tmp_path) -> None:
    session_path = tmp_path / "rollout-session-turn-context.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-06-08T14:19:01.661Z",
                "type": "turn_context",
                "payload": {
                    "cwd": "/workspace/project",
                    "model": "gpt-5",
                    "summary": "compacted context",
                    "turn_id": "turn-1",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    assert next_offset == session_path.stat().st_size
    assert len(events) == 1
    payload, _line_offset = events[0]
    assert payload["name"] == "turn_context"
    assert payload["raw_type"] == "turn_context"
    assert payload["payload"]["summary"] == "compacted context"
    assert payload["client_id"] == str(CLIENT_ID)
    assert payload["virtual_window_id"] == str(WINDOW_ID)


def test_read_new_codex_events_keeps_partial_line_unconsumed(tmp_path) -> None:
    session_path = tmp_path / "rollout-session-2.jsonl"
    complete = json.dumps({"type": "response_item", "payload": {"type": "message"}}) + "\n"
    partial = json.dumps({"type": "response_item", "payload": {"type": "reasoning"}})
    session_path.write_text(complete + partial, encoding="utf-8")

    events, next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    assert len(events) == 1
    assert events[0][0]["trace_id"] == "session-2"
    assert next_offset == len(complete.encode("utf-8"))


def test_read_new_codex_events_uses_trailing_rollout_uuid_as_session_id(tmp_path) -> None:
    session_path = tmp_path / "rollout-2026-05-21T17-38-25-019e4b9d-fdd5-7b50-956a-a0a17cdd4963.jsonl"
    session_path.write_text(
        json.dumps({"type": "response_item", "payload": {"type": "message"}}) + "\n",
        encoding="utf-8",
    )

    events, _next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    assert events[0][0]["trace_id"] == "019e4b9d-fdd5-7b50-956a-a0a17cdd4963"


def test_read_new_codex_events_uses_sidechain_session_over_rollout_path(tmp_path) -> None:
    session_path = tmp_path / "rollout-2026-06-23T09-23-56-main-session.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "isSidechain": True,
                    "agentId": "subagent-1",
                    "subagent": {"toolUseId": "call-subagent-1"},
                    "content": [{"type": "input_text", "text": "Return exactly: 1"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, _next_offset = read_new_codex_events(
        session_path,
        0,
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
    )

    payload, line_offset = events[0]
    assert line_offset == 0
    assert payload["trace_id"] == "agent-subagent-1"
    assert payload["id"] == "agent-subagent-1:0"
    assert payload["payload"]["subagent"]["toolUseId"] == "call-subagent-1"


def test_iter_recent_codex_session_files_scans_root_and_recent_day_dirs(
    tmp_path,
    monkeypatch,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 6, 9, 12, 0, 0)

    home = tmp_path / "home"
    sessions_dir = home / ".web-terminal-acp" / "codex-homes" / str(WINDOW_ID) / "sessions"
    today = FixedDateTime.now().date()
    yesterday = today - timedelta(days=1)
    older = today - timedelta(days=2)
    root_file = sessions_dir / "rollout-root.jsonl"
    today_file = sessions_dir / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}" / "rollout-today.jsonl"
    yesterday_file = (
        sessions_dir
        / f"{yesterday.year:04d}"
        / f"{yesterday.month:02d}"
        / f"{yesterday.day:02d}"
        / "rollout-yesterday.jsonl"
    )
    older_file = sessions_dir / f"{older.year:04d}" / f"{older.month:02d}" / f"{older.day:02d}" / "rollout-old.jsonl"

    for path in (root_file, today_file, yesterday_file, older_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    (today_file.parent / "ignore.txt").write_text("not jsonl", encoding="utf-8")
    (today_file.parent / "nested").mkdir()
    (today_file.parent / "nested" / "rollout-nested.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(codex_watcher, "datetime", FixedDateTime)

    assert iter_recent_codex_session_files(WINDOW_ID) == sorted([root_file, today_file, yesterday_file])
