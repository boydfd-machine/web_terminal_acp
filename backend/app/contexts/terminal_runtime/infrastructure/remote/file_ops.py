from __future__ import annotations

import asyncio
from uuid import uuid4

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionClosed
from app.contexts.terminal_runtime.domain.protocol import AgentMessage, TerminalPayload
from app.contexts.terminal_runtime.domain.types import RuntimeFileEntry
from .helpers import RemoteClientUnavailable, RemoteTerminalError, message_from_error_response


class RemoteFileOperations:
    async def read_file_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        payload: dict[str, object] = {"path": path}
        if max_bytes is not None and max_bytes > 0:
            payload["max_bytes"] = max_bytes + 1
        request = AgentMessage(
            type="file_read",
            client_id=self._client_id,
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
        if response.type != "file_read_result":
            raise RemoteTerminalError(f"unexpected file read response: {response.type}")
        payload_model = TerminalPayload.model_validate(response.payload)
        return payload_model.to_bytes()

    async def list_file_entries(self, path: str) -> list[RuntimeFileEntry]:
        response = await self._request_file(
            AgentMessage(
                type="file_list",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload={"path": path},
            ),
            expected_type="file_list_result",
        )
        entries = response.payload.get("entries")
        if not isinstance(entries, list):
            raise RemoteTerminalError("file list response missing entries")
        result: list[RuntimeFileEntry] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            entry_path = item.get("path")
            kind = item.get("kind")
            if not isinstance(name, str) or not isinstance(entry_path, str) or kind not in {"file", "directory"}:
                continue
            size = item.get("size")
            mtime = item.get("mtime")
            result.append(
                RuntimeFileEntry(
                    name=name,
                    path=entry_path,
                    kind=kind,
                    size=size if isinstance(size, int) else None,
                    mtime=mtime if isinstance(mtime, (int, float)) else None,
                )
            )
        return result

    async def write_file_bytes(self, path: str, data: bytes, *, overwrite: bool = True) -> None:
        payload = TerminalPayload.from_bytes(self._client_id, data).model_dump(mode="json")
        payload.update({"path": path, "overwrite": overwrite})
        await self._request_file(
            AgentMessage(
                type="file_write",
                client_id=self._client_id,
                request_id=str(uuid4()),
                payload=payload,
            ),
            expected_type="file_write_result",
        )

    async def _request_file(self, request: AgentMessage, *, expected_type: str) -> AgentMessage:
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
        if response.type != expected_type:
            raise RemoteTerminalError(f"unexpected file response: {response.type}")
        return response
