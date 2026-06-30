from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.mcp_acp.application.projection import mcp_client_payload, mcp_window_payload
from app.contexts.mcp_acp.domain.dispatch import (
    McpDispatchDepthExceeded,
    next_dispatch_context,
)
from app.contexts.mcp_acp.application.errors import McpAcpServiceError
from app.contexts.mcp_acp.application.source_ops_service import McpSourceOpsMixin
from app.contexts.mcp_acp.application.source_client_scope import (
    require_scoped_client,
    require_source_scope,
)
from app.contexts.mcp_acp.application.terminal_ops import map_terminal_runtime_not_ready
from app.contexts.terminal_runtime.application.connection_registry import (
    client_connection_registry_from_state,
)
from app.contexts.terminal_runtime.application.agent_prompt_input import terminal_prompt_bytes
from app.contexts.terminal_runtime.application.mcp_terminal_ops import McpTerminalRuntime
from app.contexts.terminal_runtime.application.runtime_binding import RuntimeWindowBinding
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.runtime_client import runtime_client_from_model
from app.contexts.windows.application.window_creation import create_virtual_window_for_client
from app.contexts.windows.application.window_lookup import get_window_for_client, list_active_windows
from app.models import Client, VirtualWindow
from app.platform.common_schemas import AgentLaunchIn
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.ui_events import ui_event_hub_from_state

RUNTIME_READY_TIMEOUT_SECONDS = 15.0

class McpAcpService(McpSourceOpsMixin):
    def __init__(
        self,
        *,
        session: AsyncSession,
        app_state: object,
        tmux_manager: TmuxManager,
        session_factory: Callable[[], object],
    ) -> None:
        self._session = session
        self._app_state = app_state
        self._tmux_manager = tmux_manager
        self._session_factory = session_factory

    async def list_clients(self, *, source_client_id: UUID, source_window_id: UUID) -> list[dict[str, object]]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        return [mcp_client_payload(client) for client in await scope.list_clients(self._session)]
    async def list_windows(
        self,
        client_id: UUID,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
    ) -> list[dict[str, object]]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        await scope.require_client(self._session, client_id)
        return [
            mcp_window_payload(window)
            for window in await list_active_windows(self._session)
            if window.client_id == client_id
        ]
    async def create_window(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        target_client_id: UUID,
        cwd: str | None,
        shell_command: str | None,
        agent_client: str | None,
        prompt: str | None,
        folder_path: str | None,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        try:
            derived_context = next_dispatch_context(
                source_client_id=source_client_id,
                source_window_id=source_window_id,
                source_derived_context=scope.window.derived_context,
            )
        except McpDispatchDepthExceeded as exc:
            raise McpAcpServiceError(400, str(exc)) from exc

        client = runtime_client_from_model(
            await scope.require_client(self._session, target_client_id)
        )
        try:
            result = await create_virtual_window_for_client(
                client,
                self._window_create_payload(
                    cwd=cwd,
                    shell_command=shell_command,
                    agent_client=agent_client,
                    folder_path=folder_path,
                ),
                self._session,
                self._tmux_manager,
                client_connection_registry_from_state(self._app_state),
                session_factory=self._session_factory,
                ui_event_hub=ui_event_hub_from_state(self._app_state),
            )
        except WindowServiceError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc

        result.window.derived_mode = "mcp_acp"
        result.window.derived_context = derived_context
        await self._session.commit()
        await self._session.refresh(result.window)
        await self._publish_window_created(target_client_id, result.window.id)
        if prompt is not None:
            await self._send_prompt_after_ready(
                target_client_id,
                result.window,
                prompt,
                owner_user_id=scope.owner_user_id,
            )
        return mcp_window_payload(result.window)
    async def send_input(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        target_client_id: UUID,
        window_id: UUID,
        text: str,
        append_enter: bool,
    ) -> None:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        client = await scope.require_client(self._session, target_client_id)
        window = await self._require_window(target_client_id, window_id)
        data = text.encode("utf-8") + (b"\n" if append_enter else b"")
        await map_terminal_runtime_not_ready(
            lambda: self._terminal_runtime().send_input(client=client, window=window, data=data)
        )
    async def capture_output(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        target_client_id: UUID,
        window_id: UUID,
        history_lines: int | None,
        max_bytes: int | None,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        client = await scope.require_client(self._session, target_client_id)
        window = await self._require_window(target_client_id, window_id)
        capture = await map_terminal_runtime_not_ready(
            lambda: self._terminal_runtime().capture_output(
                client=client,
                window=window,
                history_lines=history_lines,
                max_bytes=max_bytes,
            )
        )
        return {"text": capture.text, "truncated": capture.truncated}
    async def wait_for_output(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        target_client_id: UUID,
        window_id: UUID,
        contains: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
        history_lines: int | None,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        client = await scope.require_client(self._session, target_client_id)
        window = await self._require_window(target_client_id, window_id)
        capture = await map_terminal_runtime_not_ready(
            lambda: self._terminal_runtime().wait_for_output(
                client=client,
                window=window,
                contains=contains,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                history_lines=history_lines,
            )
        )
        return {"text": capture.text, "truncated": capture.truncated, "matched": contains in capture.text}
    async def _require_client(
        self,
        client_id: UUID,
        *,
        owner_user_id: str | None = None,
    ) -> Client:
        return await require_scoped_client(
            self._session,
            client_id,
            owner_user_id=owner_user_id,
        )

    async def _require_window(self, client_id: UUID, window_id: UUID) -> VirtualWindow:
        window = await get_window_for_client(self._session, client_id, window_id)
        if window is None:
            raise McpAcpServiceError(404, "window not found")
        return window

    def _window_create_payload(
        self,
        *,
        cwd: str | None,
        shell_command: str | None,
        agent_client: str | None,
        folder_path: str | None,
    ) -> WindowCreateIn:
        agent_launch = None
        if agent_client is not None:
            try:
                plugin = get_agent_plugin_registry().by_agent_id(agent_client)
            except ValueError as exc:
                raise McpAcpServiceError(400, str(exc)) from exc
            agent_launch = AgentLaunchIn(
                agent=plugin.agent_client_id,
                command=shell_command or plugin.command.default_command,
            )
            shell_command = None
        return WindowCreateIn(
            cwd=cwd,
            shell_command=shell_command,
            folder_path=folder_path,
            agent_launch=agent_launch,
        )

    def _terminal_runtime(self) -> McpTerminalRuntime:
        return McpTerminalRuntime(
            app_state=self._app_state,
            tmux_manager=self._tmux_manager,
            registry=client_connection_registry_from_state(self._app_state),
        )

    async def _publish_window_created(self, client_id: UUID, window_id: UUID) -> None:
        await ui_event_hub_from_state(self._app_state).publish_invalidation(
            ["tree", "window", "search"],
            client_id=client_id,
            window_id=window_id,
            reason="mcp_window_created",
        )

    async def _send_prompt_after_ready(
        self,
        client_id: UUID,
        window: VirtualWindow,
        prompt: str,
        *,
        owner_user_id: str | None,
    ) -> None:
        ready = await self._wait_for_runtime_ready(client_id, window.id)
        client = await self._require_client(client_id, owner_user_id=owner_user_id)
        await self._terminal_runtime().send_input(
            client=client,
            window=ready,
            data=terminal_prompt_bytes(ready.shell_command, prompt),
        )

    async def _wait_for_runtime_ready(
        self,
        client_id: UUID,
        window_id: UUID,
    ) -> VirtualWindow:
        deadline = asyncio.get_running_loop().time() + RUNTIME_READY_TIMEOUT_SECONDS
        while True:
            await self._session.rollback()
            window = await self._require_window(client_id, window_id)
            if RuntimeWindowBinding.from_virtual_window(window) is not None:
                return window
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise McpAcpServiceError(503, "terminal runtime is not ready")
            await asyncio.sleep(min(0.25, remaining))
