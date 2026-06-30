# ruff: noqa: F401
import asyncio

import json

from pathlib import Path

from uuid import UUID

import pytest

import app.client_agent.runner as client_agent_runner

from app.client_agent.__main__ import client_agent_lock

from app.client_agent.config import ClientAgentConfig, default_user_shell

from app.client_agent.runtime_window import ClientRuntimeWindow

from app.services.runtime.protocol import AgentMessage, TerminalPayload, encode_agent_message

from app.version import __version__

def _write_config(path: Path, *, server_url: str) -> None:
    path.write_text(
        json.dumps(
            {
                "client_id": "12345678-1234-5678-1234-567812345678",
                "token": "secret-token",
                "server_url": server_url,
                "name": "edge-client",
                "install_path": "/opt/web-terminal-acp-client",
            }
        ),
        encoding="utf-8",
    )

class _CollectingControlWriter:
    def __init__(self, sent_messages: list[dict[str, object]]) -> None:
        self.sent_messages = sent_messages

    async def send(self, message: AgentMessage) -> None:
        self.sent_messages.append(json.loads(encode_agent_message(message)))

class _CollectingBulkWriter:
    def __init__(self, sent_messages: list[dict[str, object]]) -> None:
        self.sent_messages = sent_messages

    async def send_terminal_output(self, message: AgentMessage) -> None:
        self.sent_messages.append(json.loads(encode_agent_message(message)))

    async def send_ai_event(self, message: AgentMessage) -> None:
        self.sent_messages.append(json.loads(encode_agent_message(message)))

class _NoopIdleSupervisor:
    def attach_view(self, view_id: UUID, window_id: UUID) -> None:
        return None

    def detach_view(self, view_id: UUID) -> None:
        return None

    def remove_window(self, window_id: UUID) -> None:
        return None

    def register_window(self, window_id: UUID, project_path: str | None) -> None:
        return None

    def has_resumable_session(self, window_id: UUID, *, project_path: str | None = None) -> bool:
        return False

    async def resume_window(self, window_id: UUID, *, allow_latest_session: bool = False) -> None:
        return None

class _NoopAgentToolWatcher:
    def watch_window(self, window_id: UUID, project_path: str | None) -> None:
        return None

    def remove_window(self, window_id: UUID) -> None:
        return None

class _NoopAuxTerminal:
    async def ensure_terminal(self, *args, **kwargs):
        return None

    async def attach(self, *args, **kwargs) -> None:
        return None

    async def detach(self, *args, **kwargs) -> None:
        return None

    async def send_input(self, *args, **kwargs) -> None:
        return None

    async def resize(self, *args, **kwargs) -> None:
        return None

class _ExistingRuntime:
    async def has_window(
        self,
        remote_window_id: str,
        *,
        remote_session_id: str | None = None,
    ) -> bool:
        return True

    async def recreate_window(
        self,
        window_id: UUID,
        *,
        cwd: str | None = None,
        shell_command: str | None = None,
    ) -> ClientRuntimeWindow:
        raise AssertionError("existing runtime window should not be recreated")

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
