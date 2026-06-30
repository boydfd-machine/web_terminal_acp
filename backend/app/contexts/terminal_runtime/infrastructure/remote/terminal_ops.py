from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionClosed
from app.contexts.terminal_runtime.domain.protocol import AgentMessage, TerminalPayload
from app.contexts.terminal_runtime.domain.types import RuntimeWindow, TerminalSelectionCallback, TerminalSender
from .helpers import (
    RemoteClientUnavailable,
    RemoteTerminalError,
    drop_none_payload_values,
    message_from_error_response,
    runtime_window_from_create_response,
    runtime_window_from_response,
)

REMOTE_CREATE_WINDOW_CONCURRENCY = 4
_REMOTE_CREATE_WINDOW_SEMAPHORE_ATTR = "_web_terminal_remote_create_window_semaphore"


class RemoteTerminalOperations:
    async def create_window(
        self,
        cwd: str | None = None,
        shell_command: str | None = None,
        *,
        window_id: UUID | None = None,
        agent_config_selection: dict[str, object] | None = None,
        system_config_files: dict[str, object] | None = None,
        agent_profile_id: str | None = None,
        agent_profile_agent: str | None = None,
        agent_model_settings: dict[str, object] | None = None,
        agent_model_agent: str | None = None,
        agent_ops_token: str | None = None,
        clone_source_window_id: UUID | str | None = None,
        isolate_clone_sessions: bool = False,
    ) -> RuntimeWindow:
        if window_id is None:
            raise ValueError("remote runtime create_window requires window_id")

        connection = self._connection()
        payload: dict[str, object] = {"cwd": cwd, "shell_command": shell_command}
        if agent_config_selection is not None:
            payload["agent_config_selection"] = agent_config_selection
        if system_config_files is not None:
            payload["system_config_files"] = system_config_files
        if agent_profile_id is not None:
            payload["agent_profile_id"] = agent_profile_id
        if agent_profile_agent is not None:
            payload["agent_profile_agent"] = agent_profile_agent
        if agent_model_settings is not None:
            payload["agent_model_settings"] = agent_model_settings
        if agent_model_agent is not None:
            payload["agent_model_agent"] = agent_model_agent
        if agent_ops_token is not None:
            payload["agent_ops_token"] = agent_ops_token
        if clone_source_window_id is not None:
            payload["clone_source_window_id"] = str(clone_source_window_id)
            if isolate_clone_sessions:
                payload["isolate_clone_sessions"] = True
        request = AgentMessage(
            type="create_window",
            client_id=self._client_id,
            window_id=window_id,
            request_id=str(uuid4()),
            payload=payload,
        )
        try:
            async with _remote_create_window_semaphore_for_connection(connection):
                response = await connection.request(request, timeout=self._request_timeout)
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="request_timeout",
            ) from exc
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))
        return runtime_window_from_create_response(response, cwd=cwd, shell_command=shell_command)

    async def attach(
        self,
        window: RuntimeWindow,
        sender: TerminalSender,
        *,
        local_window_id: object | None = None,
        selection_callback: TerminalSelectionCallback | None = None,
        view_id: UUID | str | None = None,
        allow_missing_window_recreate: bool = False,
    ) -> RuntimeWindow | None:
        if local_window_id is None:
            raise ValueError("remote runtime attach requires local_window_id")
        window_id = UUID(str(local_window_id))
        effective_view_id = UUID(str(view_id)) if view_id is not None else window_id
        request = AgentMessage(
            type="terminal_attach",
            client_id=self._client_id,
            window_id=window_id,
            request_id=str(uuid4()),
            payload={
                "remote_session_id": window.session_id,
                "remote_window_id": window.window_id,
                "view_id": str(effective_view_id),
                "cwd": window.cwd,
                "shell_command": window.shell_command,
                "activity": "terminal_viewed",
            },
        )
        if allow_missing_window_recreate:
            request.payload["allow_missing_window_recreate"] = True
        drop_none_payload_values(request.payload, "cwd", "shell_command")
        try:
            response = await self._connection().request(request, timeout=self._request_timeout)
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="request_timeout",
            ) from exc
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))
        self._sizes.pop(effective_view_id, None)
        return runtime_window_from_response(response, fallback=window)

    async def active_processes(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
    ) -> list[str]:
        if local_window_id is None:
            raise ValueError("remote runtime process liveness requires local_window_id")
        window_id = UUID(str(local_window_id))
        request = AgentMessage(
            type="process_liveness",
            client_id=self._client_id,
            window_id=window_id,
            request_id=str(uuid4()),
            payload={
                "remote_session_id": window.session_id,
                "remote_window_id": window.window_id,
            },
        )
        try:
            response = await self._connection().request(request, timeout=self._request_timeout)
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="request_timeout",
            ) from exc
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))
        raw_processes = response.payload.get("active_processes", [])
        if not isinstance(raw_processes, list):
            return []
        return [str(item) for item in raw_processes if str(item).strip()]

    async def kill_window(
        self,
        *,
        window_id: UUID,
        remote_session_id: str | None = None,
        remote_window_id: str | None = None,
    ) -> None:
        connection = self._registry.get(self._client_id)
        if connection is None or getattr(connection, "closed", False):
            return

        payload: dict[str, str] = {}
        if isinstance(remote_session_id, str):
            payload["remote_session_id"] = remote_session_id
        if isinstance(remote_window_id, str):
            payload["remote_window_id"] = remote_window_id
        request = AgentMessage(
            type="kill_window",
            client_id=self._client_id,
            window_id=window_id,
            request_id=str(uuid4()),
            payload=payload,
        )
        try:
            response = await connection.request(request, timeout=self._request_timeout)
        except (ClientConnectionClosed, asyncio.TimeoutError):
            return
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))

    async def detach(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        if local_window_id is None:
            return
        window_id = UUID(str(local_window_id))
        effective_view_id = UUID(str(view_id)) if view_id is not None else window_id
        try:
            await self._connection().send(
                AgentMessage(
                    type="terminal_detach",
                    client_id=self._client_id,
                    window_id=window_id,
                    payload={
                        "remote_session_id": window.session_id,
                        "remote_window_id": window.window_id,
                        "view_id": str(effective_view_id),
                    },
                )
            )
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        finally:
            self._sizes.pop(effective_view_id, None)

    async def send_input(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: UUID | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        if local_window_id is None:
            raise ValueError("remote runtime send_input requires local_window_id")
        effective_view_id = UUID(str(view_id)) if view_id is not None else local_window_id
        try:
            await self._connection().send(
                AgentMessage(
                    type="terminal_input",
                    client_id=self._client_id,
                    window_id=local_window_id,
                    payload={
                        **TerminalPayload.from_bytes(local_window_id, data).model_dump(mode="json"),
                        "view_id": str(effective_view_id),
                    },
                )
            )
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc

    async def send_input_direct(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: object | None = None,
    ) -> None:
        if local_window_id is None:
            raise ValueError("remote runtime direct input requires local_window_id")
        window_id = UUID(str(local_window_id))
        try:
            await self._connection().send(
                AgentMessage(
                    type="terminal_input_direct",
                    client_id=self._client_id,
                    window_id=window_id,
                    payload={
                        **TerminalPayload.from_bytes(window_id, data).model_dump(mode="json"),
                        "remote_session_id": window.session_id,
                        "remote_window_id": window.window_id,
                    },
                )
            )
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc

    async def resize(
        self,
        window: RuntimeWindow,
        *,
        cols: int,
        rows: int,
        local_window_id: UUID | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        if local_window_id is None:
            raise ValueError("remote runtime resize requires local_window_id")
        effective_view_id = UUID(str(view_id)) if view_id is not None else local_window_id
        size = (cols, rows)
        if self._sizes.get(effective_view_id) == size:
            return
        try:
            await self._connection().send(
                AgentMessage(
                    type="terminal_resize",
                    client_id=self._client_id,
                    window_id=local_window_id,
                    payload={"cols": cols, "rows": rows, "view_id": str(effective_view_id)},
                )
            )
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        self._sizes[effective_view_id] = size

    async def capture_output_bytes(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
        history_lines: int | None = None,
    ) -> bytes:
        if local_window_id is None:
            raise ValueError("remote runtime capture requires local_window_id")
        window_id = UUID(str(local_window_id))
        payload: dict[str, str] = {
            "remote_session_id": window.session_id,
            "remote_window_id": window.window_id,
        }
        if view_id is not None:
            payload["view_id"] = str(UUID(str(view_id)))
        if history_lines is not None and history_lines > 0:
            payload["history_lines"] = str(history_lines)
        request = AgentMessage(
            type="terminal_capture",
            client_id=self._client_id,
            window_id=window_id,
            request_id=str(uuid4()),
            payload=payload,
        )
        try:
            response = await self._connection().request(request, timeout=self._request_timeout)
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="request_timeout",
            ) from exc
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))
        if response.type != "terminal_capture_result":
            raise RemoteTerminalError(f"unexpected terminal capture response: {response.type}")
        payload_model = TerminalPayload.model_validate(response.payload)
        return payload_model.to_bytes()

    async def select_window(
        self,
        current_window: RuntimeWindow,
        next_window: RuntimeWindow,
        *,
        local_window_id: object,
        view_id: UUID | str | None = None,
        allow_missing_window_recreate: bool = False,
    ) -> RuntimeWindow | None:
        next_window_id = UUID(str(local_window_id))
        effective_view_id = UUID(str(view_id)) if view_id is not None else next_window_id
        request = AgentMessage(
            type="terminal_select_window",
            client_id=self._client_id,
            window_id=next_window_id,
            request_id=str(uuid4()),
            payload={
                "remote_session_id": next_window.session_id,
                "remote_window_id": next_window.window_id,
                "view_id": str(effective_view_id),
                "cwd": next_window.cwd,
                "shell_command": next_window.shell_command,
                "activity": "terminal_viewed",
            },
        )
        if allow_missing_window_recreate:
            request.payload["allow_missing_window_recreate"] = True
        drop_none_payload_values(request.payload, "cwd", "shell_command")
        try:
            response = await self._connection().request(request, timeout=self._request_timeout)
        except ClientConnectionClosed as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="connection_closed",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason="request_timeout",
            ) from exc
        if response.type == "terminal_error":
            raise RemoteTerminalError(message_from_error_response(response))
        return runtime_window_from_response(response, fallback=next_window)

def _remote_create_window_semaphore_for_connection(connection) -> asyncio.Semaphore:
    semaphore = getattr(connection, _REMOTE_CREATE_WINDOW_SEMAPHORE_ATTR, None)
    if semaphore is None:
        semaphore = asyncio.Semaphore(REMOTE_CREATE_WINDOW_CONCURRENCY)
        setattr(connection, _REMOTE_CREATE_WINDOW_SEMAPHORE_ATTR, semaphore)
    return semaphore
