from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionClosed
from app.contexts.terminal_runtime.domain.protocol import AgentMessage
from .helpers import RemoteClientUnavailable, RemoteTerminalError, message_from_error_response


class RemoteAgentOperations:
    async def get_agent_config(
        self,
        *,
        agent: str,
        window_id: UUID | None = None,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"agent": agent}
        if system_config_files is not None:
            payload["system_config_files"] = system_config_files
        response = await self._request_agent_config(
            AgentMessage(
                type="agent_config_get",
                client_id=self._client_id,
                window_id=window_id,
                request_id=str(uuid4()),
                payload=payload,
            )
        )
        return dict(response.payload)

    async def get_system_agent_config(self) -> dict[str, object]:
        response = await self._request_agent_config(
            AgentMessage(
                type="system_agent_config_get",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={},
            )
        )
        return dict(response.payload)

    async def get_agent_profile_config(
        self,
        *,
        profile_id: str,
        agent: str,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"profile_id": profile_id, "agent": agent}
        if system_config_files is not None:
            payload["system_config_files"] = system_config_files
        response = await self._request_agent_config(
            AgentMessage(
                type="agent_profile_config_get",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload=payload,
            )
        )
        return dict(response.payload)

    async def list_agent_profiles(self) -> dict[str, object]:
        response = await self._request_agent_profile(
            AgentMessage(
                type="agent_profile_list",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={},
            )
        )
        return dict(response.payload)

    async def list_agent_clients(self) -> dict[str, object]:
        response = await self._request_agent_client(
            AgentMessage(
                type="agent_clients_list",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={},
            )
        )
        return dict(response.payload)

    async def list_cursor_official_models(self) -> dict[str, object]:
        response = await self._request_agent_client(
            AgentMessage(
                type="cursor_official_models_list",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={},
            )
        )
        return dict(response.payload)

    async def create_agent_profile(
        self,
        payload: dict[str, object],
        *,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        request_payload = dict(payload)
        if system_config_files is not None:
            request_payload["system_config_files"] = system_config_files
        response = await self._request_agent_profile(
            AgentMessage(
                type="agent_profile_create",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload=request_payload,
            )
        )
        return dict(response.payload)

    async def update_agent_profile(
        self,
        profile_id: str,
        payload: dict[str, object],
        *,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        request_payload: dict[str, object] = {"profile_id": profile_id, **payload}
        if system_config_files is not None:
            request_payload["system_config_files"] = system_config_files
        response = await self._request_agent_profile(
            AgentMessage(
                type="agent_profile_update",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload=request_payload,
            )
        )
        return dict(response.payload)

    async def delete_agent_profile(self, profile_id: str) -> None:
        await self._request_agent_profile(
            AgentMessage(
                type="agent_profile_delete",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={"profile_id": profile_id},
            )
        )

    async def set_agent_profile_config_enabled(
        self,
        *,
        profile_id: str,
        agent: str,
        section_id: str,
        item_id: str,
        enabled: bool,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "profile_id": profile_id,
            "agent": agent,
            "section_id": section_id,
            "item_id": item_id,
            "enabled": enabled,
        }
        if system_config_files is not None:
            payload["system_config_files"] = system_config_files
        response = await self._request_agent_profile(
            AgentMessage(
                type="agent_profile_config_set_enabled",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload=payload,
            )
        )
        return dict(response.payload)

    async def set_agent_config_enabled(
        self,
        *,
        window_id: UUID,
        agent: str,
        section_id: str,
        item_id: str,
        enabled: bool,
        system_config_files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "agent": agent,
            "section_id": section_id,
            "item_id": item_id,
            "enabled": enabled,
        }
        if system_config_files is not None:
            payload["system_config_files"] = system_config_files
        response = await self._request_agent_config(
            AgentMessage(
                type="agent_config_set_enabled",
                client_id=self._client_id,
                window_id=window_id,
                request_id=str(uuid4()),
                payload=payload,
            )
        )
        return dict(response.payload)

    async def set_agent_config_model(
        self,
        *,
        window_id: UUID,
        agent: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        response = await self._request_agent_config(
            AgentMessage(
                type="agent_config_set_model",
                client_id=self._client_id,
                window_id=window_id,
                request_id=str(uuid4()),
                payload={"agent": agent, **payload},
            )
        )
        return dict(response.payload)

    async def _request_agent_config(self, request: AgentMessage) -> AgentMessage:
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
        if response.type != "agent_config_result":
            raise RemoteTerminalError(f"unexpected agent config response: {response.type}")
        return response

    async def _request_agent_profile(self, request: AgentMessage) -> AgentMessage:
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
        if response.type not in {"agent_profile_result", "agent_config_result"}:
            raise RemoteTerminalError(f"unexpected agent profile response: {response.type}")
        return response

    async def _request_agent_client(self, request: AgentMessage) -> AgentMessage:
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
        if response.type != "agent_client_result":
            raise RemoteTerminalError(f"unexpected agent client response: {response.type}")
        return response
