from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.api.schemas import BootstrapClientIn, BootstrapClientOut
from app.contexts.clients.infrastructure.bootstrap_installer import (
    BootstrapClientNameUnavailable,
    BootstrapConnectionError,
    BootstrapDependencyError,
    BootstrapSecretRedactor,
)
from app.contexts.clients.application.errors import ClientApiError
from app.contexts.clients.application.events import ClientUiEvents
from app.contexts.clients.infrastructure.runners import BootstrapRunner
from app.platform.auth_context import AuthIdentity
from app.platform.user_repository import upsert_user_for_identity

logger = logging.getLogger(__name__)


class ClientBootstrapService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        events: ClientUiEvents,
        auth_identity: AuthIdentity | None = None,
    ) -> None:
        self._session = session
        self._events = events
        self._auth_identity = auth_identity

    async def bootstrap_remote_client(
        self,
        payload: BootstrapClientIn,
        *,
        runner: BootstrapRunner,
    ) -> BootstrapClientOut:
        logger.info(
            "bootstrap client requested",
            extra={
                "client_name": payload.name,
                "host": payload.host,
                "port": payload.port,
                "username": payload.username,
                "server_url": payload.server_url,
            },
        )
        try:
            owner_user_id = None
            if self._auth_identity is not None and self._auth_identity.auth_provider == "keycloak":
                user = await upsert_user_for_identity(self._session, self._auth_identity)
                owner_user_id = user.id
            result = await _run_bootstrap(runner, self._session, payload, owner_user_id)
            await self._session.commit()
        except BootstrapDependencyError as exc:
            raise ClientApiError(400, _bootstrap_error_detail(payload, exc)) from None
        except BootstrapConnectionError as exc:
            raise ClientApiError(502, _bootstrap_error_detail(payload, exc)) from None
        except BootstrapClientNameUnavailable as exc:
            raise ClientApiError(409, _bootstrap_error_detail(payload, exc)) from None

        await self._events.publish(
            ["clients"],
            client_id=result.client_id,
            reason="client_bootstrapped",
        )
        logger.info(
            "bootstrap client completed",
            extra={
                "client_id": str(result.client_id),
                "client_name": result.name,
                "server_url": payload.server_url,
                "reused": result.reused,
            },
        )
        return BootstrapClientOut(
            client_id=result.client_id,
            name=result.name,
            status=result.status,
            reused=result.reused,
        )


async def _run_bootstrap(
    runner: BootstrapRunner,
    session: AsyncSession,
    payload: BootstrapClientIn,
    owner_user_id: str | None,
):
    try:
        return await runner(session, payload, owner_user_id)
    except TypeError as exc:
        if "positional" not in str(exc) and "argument" not in str(exc):
            raise
        return await runner(session, payload)  # type: ignore[misc, call-arg]


def _bootstrap_error_detail(payload: BootstrapClientIn, exc: Exception) -> str:
    return BootstrapSecretRedactor([payload.private_key, payload.passphrase]).redact(exc)
