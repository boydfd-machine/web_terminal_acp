from __future__ import annotations

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.workspace.infrastructure.project_todo_types_repository import (
    get_project_todo_type,
    list_project_todo_types,
)
from app.db import Base


@pytest.mark.asyncio
async def test_project_todo_type_default_is_synthetic_only(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'todo-types.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with session_factory() as session:
            todo_type = await get_project_todo_type(
                session,
                client_id=uuid4(),
                project_path="/workspace",
                todo_type_id="default",
            )
            assert todo_type is not None
            assert todo_type.id == "default"
            assert todo_type.name == "Default"

            assert await get_project_todo_type(
                session,
                client_id=uuid4(),
                project_path="/workspace",
                todo_type_id="ui-change",
            ) is None

            assert await list_project_todo_types(
                session,
                client_id=uuid4(),
                project_path="/workspace",
            ) == []
    finally:
        await engine.dispose()
