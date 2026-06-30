from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.api.schemas import ClientOut
from app.contexts.clients.api.projection import client_out
from app.contexts.clients.application.patches import client_patch_from_payload
from app.models import Client, ClientRuntime
from app.contexts.clients.infrastructure.repository import (
    delete_remote_client_for_owner,
    get_client_for_owner,
    get_client_by_name,
)
from app.contexts.clients.infrastructure.connections import ClientConnectionCloser
from app.contexts.clients.application.errors import ClientApiError
from app.contexts.clients.application.events import ClientUiEvents
from app.platform.auth_context import AuthIdentity
from app.platform.user_repository import upsert_user_for_identity


class ClientCrudService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        events: ClientUiEvents,
        connection_closer: ClientConnectionCloser,
        auth_identity: AuthIdentity | None = None,
    ) -> None:
        self._session = session
        self._events = events
        self._connection_closer = connection_closer
        self._auth_identity = auth_identity

    async def read_client(self, client_id: UUID) -> ClientOut:
        return client_out(await self.require_client(client_id))

    async def update_client(self, client_id: UUID, payload: object) -> ClientOut:
        client = await self.require_client(client_id)
        patch = client_patch_from_payload(payload)

        if patch.name is not None:
            existing_named_client = await get_client_by_name(self._session, patch.name)
            if existing_named_client is not None and existing_named_client.id != client_id:
                raise ClientApiError(409, "client name already exists")
            client.name = patch.name

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ClientApiError(409, "client name already exists") from None
        await self._session.refresh(client)
        await self._events.publish(
            ["clients"],
            client_id=client_id,
            reason="client_updated",
        )
        return client_out(client)

    async def delete_client(self, client_id: UUID) -> None:
        client = await self.require_client(client_id)
        if client.runtime == ClientRuntime.local:
            raise ClientApiError(400, "local client deletion unsupported")

        deleted = await delete_remote_client_for_owner(
            self._session,
            client_id,
            client.owner_user_id,
        )
        if not deleted:
            raise ClientApiError(404, "client not found")
        await self._session.commit()
        await self._connection_closer.close(client_id)
        await self._events.publish(
            ["clients", "tree", "window", "search"],
            client_id=client_id,
            reason="client_deleted",
        )

    async def require_client(self, client_id: UUID) -> Client:
        owner_user_id = None
        if self._auth_identity is not None and self._auth_identity.auth_provider == "keycloak":
            user = await upsert_user_for_identity(self._session, self._auth_identity)
            owner_user_id = user.id
        client = await get_client_for_owner(self._session, client_id, owner_user_id)
        if client is None:
            raise ClientApiError(404, "client not found")
        return client
