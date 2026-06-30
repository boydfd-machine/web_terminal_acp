from __future__ import annotations

from uuid import UUID

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry


class ClientConnectionCloser:
    def __init__(self, registry: ClientConnectionRegistry | None) -> None:
        self._registry = registry

    async def close(self, client_id: UUID) -> None:
        if self._registry is None:
            return
        connection = self._registry.get(client_id)
        if connection is None:
            return
        await connection.close()
        await self._registry.unregister(client_id, connection)
