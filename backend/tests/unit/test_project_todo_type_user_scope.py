from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.workspace.infrastructure.project_todo_types_repository import (
    list_project_todo_types,
    upsert_system_project_todo_type,
)
from app.db import Base


@pytest.mark.asyncio
async def test_custom_system_project_todo_types_are_scoped_by_owner(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'todo-types.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with session_factory() as session:
            await upsert_system_project_todo_type(
                session,
                todo_type_id="research",
                name="Alice Research",
                description=None,
                agent="codex",
                agent_profile_id=None,
                artifact_kinds=None,
                input_artifact_ids=None,
                dispatch_template=None,
                owner_user_id="alice",
            )
            await upsert_system_project_todo_type(
                session,
                todo_type_id="research",
                name="Bob Research",
                description=None,
                agent="claude",
                agent_profile_id=None,
                artifact_kinds=None,
                input_artifact_ids=None,
                dispatch_template=None,
                owner_user_id="bob",
            )
            await session.commit()

        async with session_factory() as session:
            client_id = uuid4()
            alice_types = await list_project_todo_types(
                session,
                client_id,
                "/workspace",
                owner_user_id="alice",
            )
            bob_types = await list_project_todo_types(
                session,
                client_id,
                "/workspace",
                owner_user_id="bob",
            )

        assert {todo_type.id: todo_type.name for todo_type in alice_types}["research"] == "Alice Research"
        assert {todo_type.id: todo_type.name for todo_type in bob_types}["research"] == "Bob Research"
    finally:
        await engine.dispose()
