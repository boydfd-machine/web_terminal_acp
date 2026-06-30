from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectTodo


async def next_project_todo_sort_order(session: AsyncSession, client_id: UUID, project_path: str) -> int:
    value = await session.scalar(
        select(func.max(ProjectTodo.sort_order)).where(
            ProjectTodo.client_id == client_id,
            ProjectTodo.project_path == project_path,
        )
    )
    return int(value or 0) + 1
