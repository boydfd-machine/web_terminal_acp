from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.infrastructure import project_agent_preferences_repository
from app.models import ProjectAgentPreference


async def project_agent_preferences_by_path(
    session: AsyncSession,
    client_id: UUID,
    project_paths: list[str],
) -> dict[str, ProjectAgentPreference]:
    return await project_agent_preferences_repository.project_agent_preferences_by_path(
        session,
        client_id,
        project_paths,
    )


async def get_or_create_project_agent_preference(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> ProjectAgentPreference:
    return await project_agent_preferences_repository.get_or_create_project_agent_preference(
        session,
        client_id,
        project_path,
    )


def project_agent_preference_values(
    preference: ProjectAgentPreference | None,
) -> dict[str, object]:
    return project_agent_preferences_repository.project_agent_preference_values(preference)
