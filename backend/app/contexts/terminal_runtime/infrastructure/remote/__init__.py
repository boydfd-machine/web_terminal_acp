from __future__ import annotations

from uuid import UUID

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from .agent_ops import RemoteAgentOperations
from .file_ops import RemoteFileOperations
from .helpers import RemoteClientUnavailable, RemoteTerminalError
from .terminal_ops import RemoteTerminalOperations


class RemoteRuntime(RemoteTerminalOperations, RemoteAgentOperations, RemoteFileOperations):
    def __init__(
        self,
        *,
        client_id: UUID,
        registry: ClientConnectionRegistry,
        request_timeout: float = 10.0,
    ) -> None:
        self._client_id = client_id
        self._registry = registry
        self._request_timeout = request_timeout
        self._sizes: dict[UUID, tuple[int, int]] = {}

    def _connection(self):
        connection = self._registry.get(self._client_id)
        if connection is None or getattr(connection, "closed", False):
            reason = "no_connection" if connection is None else "connection_closed"
            raise RemoteClientUnavailable(
                f"remote client unavailable: {self._client_id}",
                reason=reason,
            )
        return connection


__all__ = ["RemoteRuntime", "RemoteClientUnavailable", "RemoteTerminalError"]
