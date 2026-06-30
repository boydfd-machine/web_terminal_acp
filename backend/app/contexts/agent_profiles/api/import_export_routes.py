from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.agent_profiles.api.routes import _raise_http, _service
from app.contexts.agent_profiles.api.schemas import AgentProfileOut
from app.contexts.agent_profiles.application.api_service import AgentProfileApiError
from app.db import get_session

router = APIRouter(prefix="/api", tags=["agent-profiles"])
ProfileIdQuery = Query(..., min_length=1, max_length=128)


@router.get("/clients/{client_id}/agent-profiles/export")
async def export_client_agent_profile(
    request: Request,
    client_id: UUID,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        payload = await _service(request, session).export_profile_bundle(
            profile_id,
            client_id=client_id,
        )
        return _json_download(payload, f"{_filename_id(profile_id)}.json")
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get("/agent-profiles/export")
async def export_agent_profile(
    request: Request,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        payload = await _service(request, session).export_profile_bundle(profile_id)
        return _json_download(payload, f"{_filename_id(profile_id)}.json")
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.post("/clients/{client_id}/agent-profiles/import", response_model=AgentProfileOut)
async def import_client_agent_profile(
    request: Request,
    client_id: UUID,
    payload: dict,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).import_profile_bundle(payload, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.post("/agent-profiles/import", response_model=AgentProfileOut)
async def import_agent_profile(
    request: Request,
    payload: dict,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).import_profile_bundle(payload)
    except AgentProfileApiError as exc:
        _raise_http(exc)


def _json_download(payload: dict[str, object], filename: str) -> Response:
    return Response(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _filename_id(profile_id: str) -> str:
    return profile_id.replace("/", "-")
