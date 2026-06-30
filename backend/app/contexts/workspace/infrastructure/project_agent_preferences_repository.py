from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectAgentPreference


async def get_project_agent_preference(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> ProjectAgentPreference | None:
    return await session.scalar(
        select(ProjectAgentPreference).where(
            ProjectAgentPreference.client_id == client_id,
            ProjectAgentPreference.project_path == project_path,
        )
    )


async def project_agent_preferences_by_path(
    session: AsyncSession,
    client_id: UUID,
    project_paths: list[str],
) -> dict[str, ProjectAgentPreference]:
    if not project_paths:
        return {}
    rows = await session.scalars(
        select(ProjectAgentPreference).where(
            ProjectAgentPreference.client_id == client_id,
            ProjectAgentPreference.project_path.in_(project_paths),
        )
    )
    return {preference.project_path: preference for preference in rows}


async def get_or_create_project_agent_preference(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> ProjectAgentPreference:
    preference = await get_project_agent_preference(session, client_id, project_path)
    if preference is not None:
        return preference
    preference = ProjectAgentPreference(client_id=client_id, project_path=project_path)
    session.add(preference)
    await session.flush()
    return preference


def project_agent_preference_values(preference: ProjectAgentPreference | None) -> dict[str, object]:
    if preference is None:
        return {
            "agent_profile_id": None,
            "agent_client": None,
            "agent_command": None,
            "agent_model_selection": None,
        }
    return {
        "agent_profile_id": preference.agent_profile_id,
        "agent_client": preference.agent_client,
        "agent_command": preference.agent_command,
        "agent_model_selection": preference.agent_model_selection_json,
    }
