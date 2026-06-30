from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_agent_preference_schemas import (
    ProjectAgentPreferenceIn,
    ProjectAgentPreferenceOut,
)
from app.contexts.workspace.application.project_agent_preferences import (
    get_or_create_project_agent_preference,
    project_agent_preference_values,
)
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.db import get_session
from app.models import Client
from app.platform.polling_response_cache import invalidate_polling_response_cache_async
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api/clients/{client_id}/projects", tags=["project_agent_preferences"])

ProjectPathQuery = Query(..., min_length=1, max_length=4096)


@router.put("/agent-preference", response_model=ProjectAgentPreferenceOut)
async def update_project_agent_preference(
    client_id: UUID,
    payload: ProjectAgentPreferenceIn,
    request: Request,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectAgentPreferenceOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    preference = await get_or_create_project_agent_preference(session, client_id, normalized_path)
    preference.agent_profile_id = payload.agent_profile_id
    preference.agent_client = payload.agent_client
    preference.agent_command = payload.agent_command
    preference.agent_model_selection_json = (
        payload.agent_model_selection.model_dump(mode="json", exclude_none=True)
        if payload.agent_model_selection is not None
        else None
    )
    await session.commit()
    await session.refresh(preference)
    await invalidate_polling_response_cache_async(["project-agent-preferences"], client_id=client_id)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["projects", "project_agent_preferences"],
        client_id=client_id,
        reason="project_agent_preference_updated",
    )
    return ProjectAgentPreferenceOut(**project_agent_preference_values(preference))


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
