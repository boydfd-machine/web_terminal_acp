from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.client_agent.updater import package_checksum
from app.config import get_settings
from app.contexts.clients.domain.server_identity import RemoteClientInstance
from app.contexts.clients.infrastructure.registration_keys_repository import (
    consume_registration_key,
)
from app.contexts.clients.infrastructure.repository import (
    ClientNameUnavailable,
    create_or_rotate_remote_client_by_name,
    get_client_by_name,
)
from app.contexts.clients.infrastructure.bootstrap_installer import (
    AGENT_REQUIREMENTS,
    DEFAULT_INSTALL_PATH,
    build_client_config_payload,
    client_app_file_contents,
)
from app.models import Client, ClientRuntime, ClientStatus


class ClientRegistrationKeyInvalid(RuntimeError):
    """Raised when a direct registration key is missing, invalid, or already used."""


class ClientRegistrationNameUnavailable(RuntimeError):
    """Raised when a direct registration name cannot be assigned to a remote client."""


async def register_direct_client(
    session: AsyncSession,
    *,
    registration_key: str,
    name: str,
    hostname: str | None,
    install_path: str | None,
    server_url: str,
    owner_user_id: str | None = None,
) -> tuple[Client, str, dict[str, str], dict[str, object]]:
    base_install_path = install_path or DEFAULT_INSTALL_PATH
    instance = RemoteClientInstance.from_server_id(
        get_settings().web_terminal_server_id,
        base_install_path=base_install_path,
    )
    existing_client = await get_client_by_name(session, name)
    if existing_client is not None and existing_client.runtime == ClientRuntime.local:
        raise ClientRegistrationNameUnavailable("client name is reserved for local client")

    consumed = await consume_registration_key(
        session,
        registration_key=registration_key,
        client_id=None,
        owner_user_id=owner_user_id,
    )
    if consumed is None:
        raise ClientRegistrationKeyInvalid("registration key is invalid or already used")
    effective_owner_user_id = owner_user_id if owner_user_id is not None else consumed.owner_user_id

    try:
        client, token, _reused = await create_or_rotate_remote_client_by_name(
            session,
            name=name,
            hostname=hostname,
            install_path=instance.install_path,
            owner_user_id=effective_owner_user_id,
        )
    except ClientNameUnavailable as exc:
        raise ClientRegistrationNameUnavailable(str(exc)) from None
    consumed.used_client_id = client.id

    client.status = ClientStatus.OFFLINE
    client.last_update_at = datetime.now(UTC)
    await session.flush()
    config = build_client_config_payload(
        client,
        token=token,
        server_url=server_url,
        install_path=base_install_path,
    )
    package = build_direct_registration_package()
    return client, token, config, package


def build_direct_registration_package(job_id: str | None = None) -> dict[str, object]:
    files = client_app_file_contents()
    requirements = AGENT_REQUIREMENTS
    return {
        "job_id": job_id or str(uuid4()),
        "files": files,
        "requirements": requirements,
        "checksum": package_checksum(files, requirements),
    }
