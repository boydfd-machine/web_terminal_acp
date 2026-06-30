from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectTodo


async def child_project_todos_for_todos(
    session: AsyncSession,
    todos: list[ProjectTodo],
) -> dict[UUID, list[ProjectTodo]]:
    todo_ids = [todo.id for todo in todos]
    if not todo_ids:
        return {}
    children = list(
        await session.scalars(
            select(ProjectTodo)
            .where(ProjectTodo.parent_todo_id.in_(todo_ids))
            .order_by(desc(ProjectTodo.sort_order), desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
        )
    )
    grouped: dict[UUID, list[ProjectTodo]] = {}
    for child in children:
        if child.parent_todo_id is not None:
            grouped.setdefault(child.parent_todo_id, []).append(child)
    return grouped
