import asyncio
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import UUID
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.db import get_session
from app.main import app
from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    Event,
    EventSourceType,
    Folder,
    GitWorktreeRun,
    SummaryJob,
    SummaryJobStatus,
    TerminalRecentUsage,
    VirtualWindow,
    WindowGitBinding,
)
from app.repositories.clients import create_client, ensure_local_client
from app.contexts.windows.infrastructure.repository import create_window
from app.routers import windows as windows_router
from app.routers.windows import get_tmux_manager
from app.schemas import WindowCreateIn
from app.services import folders_api as folders_api_service
from app.services import polling_response_cache
from app.services.polling_response_cache import clear_polling_response_cache
from app.services.runtime.client_connections import ClientConnectionClosed
from app.services.runtime.protocol import AgentMessage, TerminalPayload
from app.services.window_activity_api import clear_client_windows_activity_cache

try:
    from app.db import Base
except ImportError:  # pragma: no cover - compatibility with alternate app layout
    from app.model_base import Base


class FakeTmuxManager:
    killed_targets: list[object] = []
    server_url = "https://control.example.com"

    async def create_window(
        self,
        cwd: str | None,
        shell_command: str | None,
        *,
        client_id: UUID | str | None = None,
        window_id: UUID | str | None = None,
        agent_ops_token: str | None = None,
    ):
        return type(
            "TmuxTarget", (), {"session": "test_pool", "window_id": "@99", "window_index": "4"}
        )()

    async def kill_window(self, target: object) -> None:
        self.killed_targets.append(target)

    async def window_index(self, target: object) -> str | None:
        return "4"


class CommitFailingOnSecondCallTmuxManager(FakeTmuxManager):
    commit_calls = 0


class ObservingTmuxManager(FakeTmuxManager):
    observed_in_transaction: bool | None = None

    async def create_window(
        self,
        cwd: str | None,
        shell_command: str | None,
        *,
        client_id: UUID | str | None = None,
        window_id: UUID | str | None = None,
        agent_ops_token: str | None = None,
    ):
        observed_session = getattr(windows_router, "_TEST_OBSERVED_SESSION", None)
        if observed_session is not None:
            self.__class__.observed_in_transaction = observed_session.in_transaction()
        return await super().create_window(
            cwd,
            shell_command,
            client_id=client_id,
            window_id=window_id,
            agent_ops_token=agent_ops_token,
        )


class CancellingTmuxManager(FakeTmuxManager):
    async def create_window(
        self,
        cwd: str | None,
        shell_command: str | None,
        *,
        client_id: UUID | str | None = None,
        window_id: UUID | str | None = None,
        agent_ops_token: str | None = None,
    ):
        raise asyncio.CancelledError()


class SlowTmuxManager(FakeTmuxManager):
    create_started: asyncio.Event
    create_continue: asyncio.Event

    async def create_window(
        self,
        cwd: str | None,
        shell_command: str | None,
        *,
        client_id: UUID | str | None = None,
        window_id: UUID | str | None = None,
        agent_ops_token: str | None = None,
    ):
        self.__class__.create_started.set()
        await self.__class__.create_continue.wait()
        return await super().create_window(
            cwd,
            shell_command,
            client_id=client_id,
            window_id=window_id,
            agent_ops_token=agent_ops_token,
        )


class FakeRemoteConnection:
    def __init__(self) -> None:
        self.requests: list[AgentMessage] = []
        self.sent: list[AgentMessage] = []
        self.request_started = asyncio.Event()
        self.request_continue = asyncio.Event()

    async def send(self, message: AgentMessage) -> None:
        self.sent.append(message)

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        self.request_started.set()
        await self.request_continue.wait()
        if message.type == "kill_window":
            return AgentMessage(
                type="kill_window_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={},
            )
        if message.type == "agent_clients_list":
            return AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent_clients": [
                        {
                            "id": "remote_codex",
                            "provider_id": "codex",
                            "label": "Remote Codex",
                            "aliases": [],
                            "default_command": "codex",
                            "command_names": ["codex"],
                        }
                    ]
                },
            )
        return AgentMessage(
            type="create_window_result",
            client_id=message.client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload={"remote_session_id": "remote-session", "remote_window_id": "remote-window"},
        )


class AgentConfigRemoteConnection(FakeRemoteConnection):
    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        if message.type == "agent_clients_list":
            return AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent_clients": [
                        {
                            "id": "claude",
                            "provider_id": "claude_code",
                            "label": "Remote Claude Code",
                            "aliases": ["claude_code"],
                            "default_command": "claude",
                            "command_names": ["claude"],
                        }
                    ]
                },
            )
        if message.type == "agent_config_get":
            payload = {
                "agent": "claude",
                "sections": [
                    {
                        "id": "skills",
                        "name": "Skills",
                        "items": [
                            {
                                "id": "review",
                                "name": "review",
                                "enabled": True,
                                "path": "/home/test/.claude/skills/review",
                            }
                        ],
                    },
                    {"id": "plugins", "name": "Plugins", "items": []},
                    {"id": "hooks", "name": "Hooks", "items": []},
                ],
            }
            if message.window_id is not None:
                payload["model_metadata"] = {
                    "provider": "claude_code",
                    "auto_compact_token_limit": 230000,
                }
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=payload,
            )
        if message.type == "system_agent_config_get":
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent": "system",
                    "sections": [
                        {
                            "id": "skills",
                            "name": "System Skills",
                            "items": [
                                {
                                    "id": "review-helper",
                                    "name": "Review Helper",
                                    "enabled": True,
                                    "path": None,
                                    "origin": "system_config",
                                }
                            ],
                        },
                        {
                            "id": "mcp",
                            "name": "System MCP Servers",
                            "items": [
                                {
                                    "id": "web-terminal-acp-mcp",
                                    "name": "web-terminal-acp-mcp",
                                    "enabled": True,
                                    "path": None,
                                    "origin": "system_builtin",
                                }
                            ],
                        },
                    ],
                },
            )
        if message.type == "agent_config_set_enabled":
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent": "claude",
                    "sections": [
                        {"id": "skills", "name": "Skills", "items": []},
                        {"id": "plugins", "name": "Plugins", "items": []},
                        {"id": "hooks", "name": "Hooks", "items": []},
                    ],
                },
            )
        if message.type == "agent_config_set_model":
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent": "claude",
                    "sections": [
                        {"id": "skills", "name": "Skills", "items": []},
                        {"id": "plugins", "name": "Plugins", "items": []},
                        {"id": "hooks", "name": "Hooks", "items": []},
                    ],
                    "model": {
                        "editable": True,
                        "provider": "claude_code",
                        "preset_id": "remote-preset",
                        "preset_name": "Remote",
                        "model": "claude-sonnet",
                        "available_models": ["claude-sonnet"],
                        "codex_model_reasoning_effort": None,
                        "codex_plan_mode_reasoning_effort": None,
                        "claude_reasoning_effort": "high",
                        "codex_reasoning_efforts": [],
                        "claude_reasoning_efforts": ["low", "medium", "high"],
                    },
                },
            )
        self.request_started.set()
        await self.request_continue.wait()
        if message.type == "kill_window":
            return AgentMessage(
                type="kill_window_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={},
            )
        return AgentMessage(
            type="create_window_result",
            client_id=message.client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload={"remote_session_id": "remote-session", "remote_window_id": "remote-window"},
        )


class LegacyAgentConfigRemoteConnection(AgentConfigRemoteConnection):
    def __init__(self, *, settings_json: str) -> None:
        super().__init__()
        self.settings_json = settings_json

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        if message.type == "file_read":
            self.requests.append(message)
            return AgentMessage(
                type="file_read_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=TerminalPayload.from_bytes(
                    message.client_id, self.settings_json.encode("utf-8")
                ).model_dump(mode="json"),
            )
        if message.type == "agent_config_get":
            response = await super().request(message, timeout=timeout)
            response.payload.pop("model_metadata", None)
            return response
        return await super().request(message, timeout=timeout)


class FutureAgentRemoteConnection(AgentConfigRemoteConnection):
    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        if message.type == "agent_clients_list":
            return AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent_clients": [
                        {
                            "id": "future_agent",
                            "provider_id": "future_provider",
                            "label": "Future Agent",
                            "aliases": ["future"],
                            "default_command": "future-agent",
                            "command_names": ["future-agent"],
                        }
                    ]
                },
            )
        if message.type == "agent_config_get":
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent": message.payload["agent"],
                    "sections": [
                        {"id": "skills", "name": "Skills", "items": []},
                        {"id": "plugins", "name": "Plugins", "items": []},
                        {"id": "hooks", "name": "Hooks", "items": []},
                    ],
                },
            )
        if message.type == "agent_config_set_enabled":
            return AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "agent": message.payload["agent"],
                    "sections": [
                        {"id": "skills", "name": "Skills", "items": []},
                        {"id": "plugins", "name": "Plugins", "items": []},
                        {"id": "hooks", "name": "Hooks", "items": []},
                    ],
                },
            )
        self.request_started.set()
        await self.request_continue.wait()
        return AgentMessage(
            type="create_window_result",
            client_id=message.client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload={"remote_session_id": "remote-session", "remote_window_id": "remote-window"},
        )


class CapabilityRemoteConnection(AgentConfigRemoteConnection):
    def __init__(self, capabilities: dict[str, bool]) -> None:
        super().__init__()
        self.capabilities = capabilities

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        if message.type != "agent_clients_list":
            return await super().request(message, timeout=timeout)
        self.requests.append(message)
        return AgentMessage(
            type="agent_client_result",
            client_id=message.client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload={
                "agent_clients": [
                    {
                        "id": "restricted_agent",
                        "provider_id": "restricted_provider",
                        "label": "Restricted Agent",
                        "aliases": ["restricted"],
                        "default_command": "restricted-agent",
                        "command_names": ["restricted-agent"],
                        "capabilities": self.capabilities,
                    }
                ]
            },
        )


class FailingRemoteConnection(FakeRemoteConnection):
    def __init__(self, exc: Exception) -> None:
        super().__init__()
        self.exc = exc

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        self.request_started.set()
        await self.request_continue.wait()
        raise self.exc


class TerminalErrorRemoteConnection(FakeRemoteConnection):
    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        self.request_started.set()
        await self.request_continue.wait()
        return AgentMessage(
            type="terminal_error",
            client_id=message.client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload={"message": "tmux command failed"},
        )


class ObservingRemoteConnection(FakeRemoteConnection):
    observed_in_transaction: bool | None = None

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        observed_session = getattr(windows_router, "_TEST_OBSERVED_SESSION", None)
        if observed_session is not None:
            self.__class__.observed_in_transaction = observed_session.in_transaction()
        return await super().request(message, timeout=timeout)


class FakeConnectionRegistry:
    def __init__(self, connection: FakeRemoteConnection | None = None) -> None:
        self.connection = connection
        self.requested_client_ids = []

    def get(self, client_id: UUID):
        self.requested_client_ids.append(client_id)
        return self.connection


__all__ = [name for name in globals() if not name.startswith("__")]
