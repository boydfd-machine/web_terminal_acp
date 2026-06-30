from __future__ import annotations

import asyncio
import logging

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import SessionLocal
from app.contexts.clients.api.projection import client_out
from app.contexts.clients.infrastructure.repository import list_clients_for_owner
from app.contexts.clients.infrastructure.repository import claim_unowned_clients
from app.platform.auth_context import AuthIdentity
from app.platform.user_repository import upsert_user_for_identity
from app.platform.polling_response_cache import (
    begin_response_cache_refresh,
    cached_or_stale_json_response_async,
    finish_response_cache_refresh,
    response_cache_scope,
    store_json_response_async,
)

logger = logging.getLogger(__name__)


async def list_clients(session: AsyncSession):
    return await list_clients_for_owner(session, None)


class ClientListingService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        auth_identity: AuthIdentity | None = None,
        session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    ) -> None:
        self._session = session
        self._auth_identity = auth_identity
        self._session_factory = session_factory

    async def list_clients_response(self) -> Response:
        cache_key = (
            "clients",
            response_cache_scope(self._session),
            None if self._auth_identity is None else self._auth_identity.user_id,
        )
        cached = await cached_or_stale_json_response_async(cache_key)
        if cached is not None and not cached.expired:
            return cached.response
        if cached is not None:
            self._refresh_clients_cache(cache_key)
            return cached.response
        return await self._build_clients_response()

    async def _build_clients_response(self) -> Response:
        owner_user_id = None
        if self._auth_identity is not None and self._auth_identity.auth_provider == "keycloak":
            user = await upsert_user_for_identity(self._session, self._auth_identity)
            owner_user_id = user.id
            await claim_unowned_clients(self._session, owner_user_id)
        cache_key = (
            "clients",
            response_cache_scope(self._session),
            None if self._auth_identity is None else self._auth_identity.user_id,
        )
        if owner_user_id is None:
            client_rows = await list_clients(self._session)
        else:
            client_rows = await list_clients_for_owner(self._session, owner_user_id)
        clients = [client_out(client) for client in client_rows]
        if self._auth_identity is not None:
            await self._session.commit()
        return await store_json_response_async(cache_key, clients, resources={"clients"})

    def _refresh_clients_cache(self, cache_key: tuple[object, ...]) -> None:
        if not begin_response_cache_refresh(cache_key):
            return

        async def refresh_task() -> None:
            try:
                async with self._session_factory() as refresh_session:
                    await ClientListingService(
                        refresh_session,
                        auth_identity=self._auth_identity,
                        session_factory=self._session_factory,
                    )._build_clients_response()
            except Exception:
                logger.exception("clients response cache refresh failed")
            finally:
                finish_response_cache_refresh(cache_key)

        asyncio.create_task(refresh_task())
