from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.platform.auth_context import AuthIdentity


async def upsert_user_for_identity(session: AsyncSession, identity: AuthIdentity) -> User:
    user = await session.get(User, identity.user_id)
    if user is None:
        user = await session.scalar(
            select(User).where(
                User.auth_provider == identity.auth_provider,
                User.subject == identity.user_id,
            )
        )
    if user is None:
        user = User(
            id=identity.user_id,
            auth_provider=identity.auth_provider,
            subject=identity.user_id,
        )
        session.add(user)
    user.username = identity.username
    user.email = identity.email
    user.display_name = identity.display_name
    await session.flush()
    return user
