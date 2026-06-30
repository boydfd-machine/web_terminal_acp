from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.api.schemas import ClientRegistrationKeyOut, DirectClientRegisterOut
from app.contexts.clients.infrastructure.registration_keys_repository import create_registration_key
from app.contexts.clients.application.errors import ClientApiError
from app.contexts.clients.application.events import ClientUiEvents
from app.contexts.clients.application.direct_registration import (
    ClientRegistrationKeyInvalid,
    ClientRegistrationNameUnavailable,
    register_direct_client,
)
from app.platform.auth_context import AuthIdentity
from app.platform.user_repository import upsert_user_for_identity


class ClientRegistrationService:
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

    async def create_registration_key(self, *, label: str | None) -> ClientRegistrationKeyOut:
        owner_user_id = await self._owner_user_id()
        registration_key, key = await create_registration_key(
            self._session,
            label=label,
            owner_user_id=owner_user_id,
        )
        await self._session.commit()
        await self._session.refresh(registration_key)
        return ClientRegistrationKeyOut(
            id=registration_key.id,
            key=key,
            label=registration_key.label,
            created_at=registration_key.created_at,
        )

    async def register_direct_client(
        self,
        *,
        registration_key: str,
        name: str,
        hostname: str | None,
        install_path: str | None,
        server_url: str,
    ) -> DirectClientRegisterOut:
        try:
            owner_user_id = await self._owner_user_id()
            client, token, config, package = await register_direct_client(
                self._session,
                registration_key=registration_key,
                name=name,
                hostname=hostname,
                install_path=install_path,
                server_url=server_url,
                owner_user_id=owner_user_id,
            )
        except ClientRegistrationKeyInvalid as exc:
            raise ClientApiError(401, str(exc)) from None
        except ClientRegistrationNameUnavailable as exc:
            raise ClientApiError(409, str(exc)) from None
        await self._session.commit()
        await self._events.publish(
            ["clients"],
            client_id=client.id,
            reason="client_registered",
        )
        return DirectClientRegisterOut(
            client_id=client.id,
            token=token,
            name=client.name,
            config=config,
            package=package,
        )

    async def _owner_user_id(self) -> str | None:
        if self._auth_identity is None or self._auth_identity.auth_provider != "keycloak":
            return None
        user = await upsert_user_for_identity(self._session, self._auth_identity)
        return user.id
