from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.domain.project_todo_type_defaults import (
    DEFAULT_PROJECT_TODO_TYPE,
    DEFAULT_PROJECT_TODO_TYPE_ID,
)
from app.models import Client, ProjectTodo, ProjectTodoType

_DEFAULT_PROJECT_TODO_TYPE_CREATED_AT = datetime(2000, 1, 1, tzinfo=UTC)


async def ensure_default_project_todo_type(session: AsyncSession) -> ProjectTodoType:
    existing = await session.scalar(
        select(ProjectTodoType).where(
            ProjectTodoType.scope == "system",
            ProjectTodoType.id == DEFAULT_PROJECT_TODO_TYPE_ID,
        )
    )
    if existing is not None:
        return existing
    return _default_project_todo_type()


async def list_project_todo_types(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    owner_user_id: str | None = None,
) -> list[ProjectTodoType]:
    owner_user_id = owner_user_id if owner_user_id is not None else await _client_owner_user_id(session, client_id)
    system_filters = [ProjectTodoType.scope == "system"]
    if owner_user_id is None:
        system_filters.append(ProjectTodoType.owner_user_id.is_(None))
    else:
        system_filters.append(
            (ProjectTodoType.owner_user_id.is_(None))
            | (ProjectTodoType.owner_user_id == owner_user_id)
        )
    system_filters.append(ProjectTodoType.id != DEFAULT_PROJECT_TODO_TYPE_ID)
    system_rows = list(await session.scalars(select(ProjectTodoType).where(*system_filters)))
    system_by_id: dict[str, ProjectTodoType] = {}
    for todo_type in system_rows:
        if todo_type.owner_user_id is None:
            system_by_id.setdefault(todo_type.id, todo_type)
        else:
            system_by_id[todo_type.id] = todo_type
    system_types = list(system_by_id.values())
    project_types = list(
        await session.scalars(
            select(ProjectTodoType).where(
                ProjectTodoType.scope == "project",
                ProjectTodoType.client_id == client_id,
                ProjectTodoType.project_path == project_path,
            )
        )
    )
    return sorted(
        [*system_types, *project_types],
        key=lambda todo_type: (
            0 if todo_type.scope == "system" else 1,
            todo_type.name.lower(),
            todo_type.id.lower(),
        ),
    )


async def get_project_todo_type(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    todo_type_id: str,
    owner_user_id: str | None = None,
) -> ProjectTodoType | None:
    await ensure_default_project_todo_type(session)
    owner_user_id = owner_user_id if owner_user_id is not None else await _client_owner_user_id(session, client_id)
    project_type = await session.scalar(
        select(ProjectTodoType).where(
            ProjectTodoType.scope == "project",
            ProjectTodoType.client_id == client_id,
            ProjectTodoType.project_path == project_path,
            ProjectTodoType.id == todo_type_id,
        )
    )
    if project_type is not None:
        return project_type
    if owner_user_id is not None:
        user_system_type = await session.scalar(
            select(ProjectTodoType).where(
                ProjectTodoType.scope == "system",
                ProjectTodoType.owner_user_id == owner_user_id,
                ProjectTodoType.id == todo_type_id,
            )
        )
        if user_system_type is not None:
            return user_system_type
    system_type = await session.scalar(
        select(ProjectTodoType).where(
            ProjectTodoType.scope == "system",
            ProjectTodoType.owner_user_id.is_(None),
            ProjectTodoType.id == todo_type_id,
        )
    )
    if system_type is not None:
        return system_type
    if todo_type_id == DEFAULT_PROJECT_TODO_TYPE_ID:
        return await ensure_default_project_todo_type(session)
    return None


async def todo_type_map_for_todos(
    session: AsyncSession,
    todos: list[ProjectTodo],
) -> dict[UUID, ProjectTodoType]:
    if not todos:
        return {}
    default_type = await ensure_default_project_todo_type(session)
    groups: dict[tuple[UUID, str], list[ProjectTodo]] = defaultdict(list)
    for todo in todos:
        groups[(todo.client_id, todo.project_path)].append(todo)

    resolved: dict[UUID, ProjectTodoType] = {}
    for (client_id, project_path), group in groups.items():
        todo_types = await list_project_todo_types(session, client_id, project_path)
        type_by_id: dict[str, ProjectTodoType] = {}
        for todo_type in todo_types:
            type_by_id[todo_type.id] = todo_type
        for todo in group:
            resolved[todo.id] = type_by_id.get(todo.todo_type_id, default_type)
    return resolved


async def upsert_system_project_todo_type(
    session: AsyncSession,
    *,
    todo_type_id: str,
    name: str,
    description: str | None,
    agent: str | None,
    agent_profile_id: str | None,
    artifact_kinds: list[str] | None,
    input_artifact_ids: list[str] | None,
    dispatch_template: str | None,
    owner_user_id: str | None = None,
) -> ProjectTodoType:
    existing = await session.scalar(
        select(ProjectTodoType).where(
            ProjectTodoType.scope == "system",
            ProjectTodoType.owner_user_id.is_(None)
            if owner_user_id is None
            else ProjectTodoType.owner_user_id == owner_user_id,
            ProjectTodoType.id == todo_type_id,
        )
    )
    if existing is None:
        existing = ProjectTodoType(
            id=todo_type_id,
            scope="system",
            owner_user_id=owner_user_id,
            name=name,
        )
        session.add(existing)
    existing.name = name
    existing.description = description
    existing.agent = agent
    existing.agent_profile_id = agent_profile_id
    existing.artifact_kinds_json = artifact_kinds or None
    existing.input_artifact_ids_json = input_artifact_ids or None
    existing.dispatch_template = dispatch_template
    await session.flush()
    await session.refresh(existing)
    return existing


async def patch_system_project_todo_type(
    session: AsyncSession,
    todo_type_id: str,
    *,
    name: str | None = None,
    description_provided: bool = False,
    description: str | None = None,
    agent_provided: bool = False,
    agent: str | None = None,
    agent_profile_id_provided: bool = False,
    agent_profile_id: str | None = None,
    artifact_kinds_provided: bool = False,
    artifact_kinds: list[str] | None = None,
    input_artifact_ids_provided: bool = False,
    input_artifact_ids: list[str] | None = None,
    dispatch_template_provided: bool = False,
    dispatch_template: str | None = None,
    owner_user_id: str | None = None,
) -> ProjectTodoType | None:
    todo_type = await session.scalar(
        select(ProjectTodoType).where(
            ProjectTodoType.scope == "system",
            ProjectTodoType.owner_user_id.is_(None)
            if owner_user_id is None
            else ProjectTodoType.owner_user_id == owner_user_id,
            ProjectTodoType.id == todo_type_id,
        )
    )
    if todo_type is None:
        return None
    if name is not None:
        todo_type.name = name
    if description_provided:
        todo_type.description = description
    if agent_provided:
        todo_type.agent = agent
    if agent_profile_id_provided:
        todo_type.agent_profile_id = agent_profile_id
    if artifact_kinds_provided:
        todo_type.artifact_kinds_json = artifact_kinds or None
    if input_artifact_ids_provided:
        todo_type.input_artifact_ids_json = input_artifact_ids or None
    if dispatch_template_provided:
        todo_type.dispatch_template = dispatch_template
    await session.flush()
    await session.refresh(todo_type)
    return todo_type


async def delete_system_project_todo_type(
    session: AsyncSession,
    todo_type_id: str,
    *,
    owner_user_id: str | None = None,
) -> bool:
    if todo_type_id == DEFAULT_PROJECT_TODO_TYPE_ID:
        return False
    todo_filters = [ProjectTodo.todo_type_id == todo_type_id]
    if owner_user_id is not None:
        todo_filters.append(
            ProjectTodo.client_id.in_(
                select(Client.id).where(Client.owner_user_id == owner_user_id)
            )
        )
    existing_todo = await session.scalar(
        select(ProjectTodo.id).where(*todo_filters).limit(1)
    )
    if existing_todo is not None:
        raise ValueError("todo type is in use")
    result = await session.execute(
        delete(ProjectTodoType).where(
            ProjectTodoType.scope == "system",
            ProjectTodoType.owner_user_id.is_(None)
            if owner_user_id is None
            else ProjectTodoType.owner_user_id == owner_user_id,
            ProjectTodoType.id == todo_type_id,
        )
    )
    await session.flush()
    return bool(result.rowcount)


async def _client_owner_user_id(session: AsyncSession, client_id: UUID) -> str | None:
    return await session.scalar(select(Client.owner_user_id).where(Client.id == client_id))


def _default_project_todo_type() -> ProjectTodoType:
    return ProjectTodoType(
        record_id=DEFAULT_PROJECT_TODO_TYPE.record_id,
        id=DEFAULT_PROJECT_TODO_TYPE.id,
        scope="system",
        name=DEFAULT_PROJECT_TODO_TYPE.name,
        description=DEFAULT_PROJECT_TODO_TYPE.description,
        agent=DEFAULT_PROJECT_TODO_TYPE.agent,
        agent_profile_id=DEFAULT_PROJECT_TODO_TYPE.agent_profile_id,
        artifact_kinds_json=list(DEFAULT_PROJECT_TODO_TYPE.artifact_kinds) or None,
        input_artifact_ids_json=None,
        dispatch_template=DEFAULT_PROJECT_TODO_TYPE.dispatch_template,
        created_at=_DEFAULT_PROJECT_TODO_TYPE_CREATED_AT,
        updated_at=_DEFAULT_PROJECT_TODO_TYPE_CREATED_AT,
    )
