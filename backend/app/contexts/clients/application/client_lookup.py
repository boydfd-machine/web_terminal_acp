from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.infrastructure.repository import (
    ensure_local_client,
    get_client_for_owner,
    list_clients,
    list_clients_for_owner,
)
from app.models import Client
from app.platform.auth_context import current_auth_identity
from app.platform.user_repository import upsert_user_for_identity


async def get_client(session: AsyncSession, client_id: UUID) -> Client | None:
    identity = current_auth_identity()
    if identity is None or identity.auth_provider != "keycloak":
        return await get_client_for_owner(session, client_id, None)
    user = await upsert_user_for_identity(session, identity)
    return await get_client_for_owner(session, client_id, user.id)


async def get_client_owned_by(
    session: AsyncSession,
    client_id: UUID,
    owner_user_id: str | None,
) -> Client | None:
    return await get_client_for_owner(session, client_id, owner_user_id)


async def list_clients_owned_by(
    session: AsyncSession,
    owner_user_id: str | None,
) -> list[Client]:
    return await list_clients_for_owner(session, owner_user_id)


__all__ = [
    "ensure_local_client",
    "get_client",
    "get_client_owned_by",
    "list_clients",
    "list_clients_owned_by",
]
