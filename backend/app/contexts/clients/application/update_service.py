from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.domain import BearerToken, ClientUpdateCompletion
from app.contexts.clients.api.schemas import ClientUpdateOut
from app.contexts.clients.application.client_update import (
    ClientUpdateUnavailable,
    build_client_update_package,
)
from app.contexts.clients.application.crud_service import ClientCrudService
from app.contexts.clients.application.errors import ClientApiError
from app.contexts.clients.application.events import ClientUiEvents
from app.contexts.clients.infrastructure.runners import UpdateRunner
from app.contexts.clients.infrastructure.repository import authenticate_client
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.models import ClientRuntime

logger = logging.getLogger(__name__)


class ClientUpdateService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        events: ClientUiEvents,
        crud: ClientCrudService,
        connection_registry: ClientConnectionRegistry | None,
    ) -> None:
        self._session = session
        self._events = events
        self._crud = crud
        self._connection_registry = connection_registry

    async def start_remote_client_update(
        self,
        client_id: UUID,
        *,
        runner: UpdateRunner,
    ) -> ClientUpdateOut:
        client = await self._crud.require_client(client_id)
        if client.runtime == ClientRuntime.local:
            raise ClientApiError(400, "local client update unsupported")

        try:
            result = await runner(client_id, self._require_connection_registry())
        except ClientUpdateUnavailable as exc:
            raise ClientApiError(409, str(exc)) from None

        await self._events.publish(
            ["clients"],
            client_id=client_id,
            reason="client_update_started",
        )
        return ClientUpdateOut(
            client_id=result.client_id,
            job_id=result.job_id,
            status=result.status,
            method=result.method,
        )

    async def read_update_package(
        self,
        client_id: UUID,
        *,
        job_id: str | None,
        authorization: str | None,
    ) -> dict[str, object]:
        await self._authenticate_client_or_raise(client_id, authorization)
        return build_client_update_package(job_id)

    async def complete_client_update(
        self,
        client_id: UUID,
        payload: object,
        *,
        authorization: str | None,
    ) -> dict[str, object]:
        client = await self._authenticate_client_or_raise(client_id, authorization)
        completion = ClientUpdateCompletion.now(job_id=getattr(payload, "job_id", None))
        client.last_update_at = completion.completed_at
        await self._session.commit()
        await self._events.publish(
            ["clients"],
            client_id=client_id,
            reason="client_update_completed",
        )
        logger.info(
            "client update completed",
            extra={
                "client_id": str(client_id),
                "job_id": completion.job_id,
                "completed_at": completion.completed_at.isoformat(),
            },
        )
        return completion.response_payload(client_id=client_id)

    async def _authenticate_client_or_raise(self, client_id: UUID, authorization: str | None):
        bearer = BearerToken.parse(authorization)
        client = (
            None
            if bearer is None
            else await authenticate_client(self._session, client_id, bearer.value)
        )
        if client is None:
            raise ClientApiError(401, "invalid client token")
        return client

    def _require_connection_registry(self) -> ClientConnectionRegistry:
        if self._connection_registry is None:
            raise RuntimeError("client connection registry is required")
        return self._connection_registry
