from __future__ import annotations

from uuid import UUID

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import SessionLocal
from app.contexts.clients.api.schemas import (
    BootstrapClientIn,
    BootstrapClientOut,
    ClientOut,
    ClientRegistrationKeyOut,
    ClientUpdateOut,
    DirectClientRegisterOut,
)
from app.contexts.clients.application.bootstrap_service import ClientBootstrapService
from app.contexts.clients.infrastructure.connections import ClientConnectionCloser
from app.contexts.clients.application.crud_service import ClientCrudService
from app.contexts.clients.application.events import ClientUiEvents
from app.contexts.clients.application.listing_service import ClientListingService
from app.contexts.clients.application.registration_service import ClientRegistrationService
from app.contexts.clients.infrastructure.runners import (
    BootstrapRunner,
    UpdateRunner,
    default_bootstrap_runner,
)
from app.contexts.clients.application.update_service import ClientUpdateService
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.platform.auth_context import current_auth_identity


class ClientApiService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        app_state: object | None = None,
        connection_registry: ClientConnectionRegistry | None = None,
        session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    ) -> None:
        auth_identity = current_auth_identity()
        events = ClientUiEvents(app_state)
        connection_closer = ClientConnectionCloser(connection_registry)
        crud = ClientCrudService(
            session,
            events=events,
            connection_closer=connection_closer,
            auth_identity=auth_identity,
        )

        self._bootstrap = ClientBootstrapService(session, events=events, auth_identity=auth_identity)
        self._crud = crud
        self._listing = ClientListingService(
            session,
            auth_identity=auth_identity,
            session_factory=session_factory,
        )
        self._registration = ClientRegistrationService(
            session,
            events=events,
            auth_identity=auth_identity,
        )
        self._update = ClientUpdateService(
            session,
            events=events,
            crud=crud,
            connection_registry=connection_registry,
        )

    async def list_clients_response(self) -> Response:
        return await self._listing.list_clients_response()

    async def bootstrap_remote_client(
        self,
        payload: BootstrapClientIn,
        *,
        runner: BootstrapRunner = default_bootstrap_runner(),
    ) -> BootstrapClientOut:
        return await self._bootstrap.bootstrap_remote_client(payload, runner=runner)

    async def create_registration_key(self, *, label: str | None) -> ClientRegistrationKeyOut:
        return await self._registration.create_registration_key(label=label)

    async def register_direct_client(
        self,
        *,
        registration_key: str,
        name: str,
        hostname: str | None,
        install_path: str | None,
        server_url: str,
    ) -> DirectClientRegisterOut:
        return await self._registration.register_direct_client(
            registration_key=registration_key,
            name=name,
            hostname=hostname,
            install_path=install_path,
            server_url=server_url,
        )

    async def start_remote_client_update(
        self,
        client_id: UUID,
        *,
        runner: UpdateRunner,
    ) -> ClientUpdateOut:
        return await self._update.start_remote_client_update(client_id, runner=runner)

    async def read_update_package(
        self,
        client_id: UUID,
        *,
        job_id: str | None,
        authorization: str | None,
    ) -> dict[str, object]:
        return await self._update.read_update_package(
            client_id,
            job_id=job_id,
            authorization=authorization,
        )

    async def complete_client_update(
        self,
        client_id: UUID,
        payload: object,
        *,
        authorization: str | None,
    ) -> dict[str, object]:
        return await self._update.complete_client_update(
            client_id,
            payload,
            authorization=authorization,
        )

    async def read_client(self, client_id: UUID) -> ClientOut:
        return await self._crud.read_client(client_id)

    async def update_client(self, client_id: UUID, payload: object) -> ClientOut:
        return await self._crud.update_client(client_id, payload)

    async def delete_client(self, client_id: UUID) -> None:
        await self._crud.delete_client(client_id)
