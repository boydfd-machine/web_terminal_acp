from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.schemas import ProjectReviewConfigOut, ProjectReviewConfigPutIn
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_review_configs import (
    get_or_create_project_review_config,
    project_review_config_values,
)
from app.db import get_session
from app.models import Client
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api/clients/{client_id}/projects", tags=["project_review_configs"])

ProjectPathQuery = Query(..., min_length=1, max_length=4096)


@router.get("/review-config", response_model=ProjectReviewConfigOut)
async def read_project_review_config(
    client_id: UUID,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectReviewConfigOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    config = await get_or_create_project_review_config(session, client_id, normalized_path)
    await session.commit()
    await session.refresh(config)
    return ProjectReviewConfigOut(**project_review_config_values(config))


@router.put("/review-config", response_model=ProjectReviewConfigOut)
async def update_project_review_config(
    client_id: UUID,
    payload: ProjectReviewConfigPutIn,
    request: Request,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectReviewConfigOut:
    await _require_client(session, client_id)
    normalized_path = _normalize_project_path(project_path)
    config = await get_or_create_project_review_config(session, client_id, normalized_path)
    config.pr_provider = payload.pr_provider
    config.pr_provider_config_json = payload.pr_provider_config
    config.review_agent = payload.review_agent
    config.review_agent_command = payload.review_agent_command
    config.review_agent_profile_id = payload.review_agent_profile_id
    config.auto_create_review_target = payload.auto_create_review_target
    config.auto_dispatch_review = payload.auto_dispatch_review
    config.merge_policy = payload.merge_policy
    config.required_artifact_kinds_json = payload.required_artifact_kinds
    await session.commit()
    await session.refresh(config)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["project_review_config", "project_todos"],
        client_id=client_id,
        reason="project_review_config_updated",
    )
    return ProjectReviewConfigOut(**project_review_config_values(config))


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
