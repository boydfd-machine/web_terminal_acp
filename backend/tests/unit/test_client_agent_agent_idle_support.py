from __future__ import annotations

import json

import os

import sqlite3

from pathlib import Path

from uuid import UUID

import pytest

from app.client_agent.agent_idle import (
    AgentIdleSupervisor,
    SuspendedAgent,
    latest_resume_command,
    latest_antigravity_session_ref,
    latest_claude_session_ref,
    latest_codex_session_ref,
    latest_cursor_session_ref,
    resume_command,
    session_id_from_payload,
    session_ref_from_event,
)

from app.client_agent.agent_work_presence import AgentProcess

from app.client_agent.ai_events import ManagedAiEvent

WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")

class FakeTerminal:
    def __init__(self) -> None:
        self.targets: dict[UUID, str] = {WINDOW_ID: "pool:@7"}

    def tmux_target_for(self, window_id: UUID) -> str | None:
        return self.targets.get(window_id)

class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def _run(self, args: list[str]) -> str:
        self.calls.append(args)
        return ""

def write_cursor_store(path: Path, *, agent_id: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("create table meta (key TEXT PRIMARY KEY, value TEXT)")
    meta = {"agentId": agent_id, "latestRootBlobId": "root-1"}
    conn.execute("insert into meta (key, value) values (?, ?)", ("0", json.dumps(meta).encode().hex()))
    conn.commit()
    conn.close()

__all__ = [name for name in globals() if not name.startswith("__")]
