from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import (
    get_client,
    get_client_owned_by,
    list_clients,
    list_clients_owned_by,
)
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.contexts.mcp_acp.application.errors import McpAcpServiceError
from app.models import Client, VirtualWindow


@dataclass(frozen=True)
class SourceClientScope:
    window: VirtualWindow
    owner_user_id: str | None

    async def require_client(self, session: AsyncSession, client_id: UUID) -> Client:
        return await require_scoped_client(session, client_id, owner_user_id=self.owner_user_id)

    async def list_clients(self, session: AsyncSession) -> list[Client]:
        if self.owner_user_id is None:
            return await list_clients(session)
        return await list_clients_owned_by(session, self.owner_user_id)


async def require_source_scope(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
) -> SourceClientScope:
    client = await require_scoped_client(session, client_id, owner_user_id=None)
    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise McpAcpServiceError(404, "window not found")
    return SourceClientScope(window=window, owner_user_id=client.owner_user_id)


async def require_scoped_client(
    session: AsyncSession,
    client_id: UUID,
    *,
    owner_user_id: str | None,
) -> Client:
    client = (
        await get_client(session, client_id)
        if owner_user_id is None
        else await get_client_owned_by(session, client_id, owner_user_id)
    )
    if client is None:
        raise McpAcpServiceError(404, "client not found")
    return client
