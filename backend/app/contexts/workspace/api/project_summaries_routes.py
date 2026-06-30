from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.api.schemas import ProjectSummaryOut, ProjectSummarySummarizeIn
from app.contexts.workspace.application.project_summaries_service import (
    ProjectSummaryApiError,
    ProjectSummaryApiService,
)
from app.contexts.workspace.application.project_summarizer import ProjectSummarizer
from app.contexts.workspace.domain.project_summaries import ProjectSummaryRequest
from app.db import get_session

router = APIRouter(prefix="/api/clients", tags=["project-summaries"])


def _service(session: AsyncSession) -> ProjectSummaryApiService:
    return ProjectSummaryApiService(session, summarizer_factory=ProjectSummarizer)


def _raise_http(exc: ProjectSummaryApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/{client_id}/project-summaries", response_model=list[ProjectSummaryOut])
async def get_project_summaries(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSummaryOut]:
    try:
        return await _service(session).list_summaries(client_id)
    except ProjectSummaryApiError as exc:
        _raise_http(exc)


@router.post("/{client_id}/project-summaries/summarize", response_model=ProjectSummaryOut)
async def summarize_project(
    client_id: UUID,
    payload: ProjectSummarySummarizeIn,
    session: AsyncSession = Depends(get_session),
) -> ProjectSummaryOut:
    try:
        request = ProjectSummaryRequest.from_payload(payload)
        return await _service(session).summarize_project(client_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProjectSummaryApiError as exc:
        _raise_http(exc)
