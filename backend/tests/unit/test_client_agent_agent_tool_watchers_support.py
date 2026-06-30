from __future__ import annotations

import asyncio

import json

import os

import sqlite3

import threading

from pathlib import Path

from uuid import UUID

import pytest

import app.client_agent.agent_tool_watchers as watchers

from app.client_agent.agent_tool_watchers import (
    AGENT_TOOL_COLLECTORS,
    AgentToolWatcherState,
    UnifiedAgentToolWatcher,
    _collect_all_events,
    collect_claude_code_watch_events,
    collect_codex_watch_events,
    collect_cursor_watch_events,
    enqueue_managed_ai_event,
    initialize_agent_tool_watcher_state,
    read_all_claude_history_session_ids,
    read_claude_history_session_ids,
    watch_agent_tool_events,
)

from app.services.runtime.protocol import AgentMessage

CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")

WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

def write_cursor_store(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("create table meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("create table blobs (id TEXT PRIMARY KEY, data BLOB)")
    meta = {
        "agentId": "cursor-agent-1",
        "latestRootBlobId": "root-1",
        "name": "Cursor Test Chat",
        "createdAt": 1779520336671,
        "lastUsedModel": "default",
    }
    conn.execute("insert into meta (key, value) values (?, ?)", ("0", json.dumps(meta).encode("utf-8").hex()))
    conn.execute(
        "insert into blobs (id, data) values (?, ?)",
        (
            "user-blob",
            json.dumps({"role": "user", "content": [{"type": "text", "text": "hi"}]}).encode("utf-8"),
        ),
    )
    conn.execute(
        "insert into blobs (id, data) values (?, ?)",
        ("assistant-blob", json.dumps({"role": "assistant", "content": "hello"}).encode("utf-8")),
    )
    conn.execute("insert into blobs (id, data) values (?, ?)", ("binary-blob", b"\x0a\x02hi"))
    conn.commit()
    conn.close()

def append_cursor_blob(path: Path, blob_id: str, role: str, text: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "insert into blobs (id, data) values (?, ?)",
        (blob_id, json.dumps({"role": role, "content": text}).encode("utf-8")),
    )
    conn.commit()
    conn.close()

class FakeIdleSupervisor:
    def __init__(self) -> None:
        self.observed_batches: list[list[object]] = []
        self.checked_windows: list[UUID] = []

    async def observe_events(self, events):
        self.observed_batches.append(events)

    async def maybe_suspend_window(self, window_id: UUID) -> None:
        self.checked_windows.append(window_id)

__all__ = [name for name in globals() if not name.startswith("__")]
