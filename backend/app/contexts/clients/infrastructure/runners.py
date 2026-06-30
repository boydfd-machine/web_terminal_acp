from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.api.schemas import BootstrapClientIn
from app.contexts.clients.application.client_update import (
    ClientUpdateStartResult,
    start_client_update,
)
from app.contexts.clients.infrastructure.bootstrap_installer import BootstrapResult, bootstrap_client
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry

BootstrapRunner = Callable[[AsyncSession, BootstrapClientIn, str | None], Awaitable[BootstrapResult]]
UpdateRunner = Callable[[UUID, ClientConnectionRegistry], Awaitable[ClientUpdateStartResult]]


def default_bootstrap_runner() -> BootstrapRunner:
    async def runner(
        session: AsyncSession,
        payload: BootstrapClientIn,
        owner_user_id: str | None = None,
    ) -> BootstrapResult:
        return await bootstrap_client(session, payload, owner_user_id=owner_user_id)

    return runner


def default_update_runner() -> UpdateRunner:
    async def runner(client_id: UUID, registry: ClientConnectionRegistry) -> ClientUpdateStartResult:
        return await start_client_update(client_id, registry=registry)

    return runner
