from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.infrastructure.repository import authenticate_client


async def authenticate_client_token(session: AsyncSession, client_id: UUID, token: str):
    return await authenticate_client(session, client_id, token)
