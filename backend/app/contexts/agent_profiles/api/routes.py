from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.contexts.agent_profiles.domain import AgentProfileUpdate
from app.contexts.agent_profiles.api.schemas import (
    AgentConfigOut,
    AgentConfigToggleIn,
    AgentProfileCreateIn,
    AgentProfileListOut,
    AgentProfileOut,
    AgentProfileUpdateIn,
    SystemMcpServerUpsertIn,
)
from app.contexts.agent_profiles.application.api_service import AgentProfileApiError, AgentProfileApiService
from app.contexts.agent_profiles.application.config_projection import agent_config_out
from app.contexts.agent_profiles.application import system_config as system_config_service
from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state

router = APIRouter(prefix="/api", tags=["agent-profiles"])
ProfileIdQuery = Query(..., min_length=1, max_length=128)


def _service(request: Request, session: AsyncSession) -> AgentProfileApiService:
    return AgentProfileApiService(
        session=session,
        registry=client_connection_registry_from_state(request.app.state),
    )


def _raise_http(exc: AgentProfileApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/clients/{client_id}/agent-profiles", response_model=AgentProfileListOut)
async def read_client_agent_profiles(
    request: Request,
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileListOut:
    try:
        return await _service(request, session).list_profiles(client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)

@router.get("/agent-profiles", response_model=AgentProfileListOut)
async def read_agent_profiles(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileListOut:
    try:
        return await _service(request, session).list_profiles()
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get("/system-agent-config", response_model=AgentConfigOut)
async def read_system_agent_config(
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    config = await system_config_service.list_system_agent_config(session)
    await session.commit()
    return agent_config_out(config)


@router.patch("/system-agent-config/{section_id}/{item_id:path}", response_model=AgentConfigOut)
async def update_system_agent_config_item(
    section_id: str,
    item_id: str,
    payload: AgentConfigToggleIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        config = await system_config_service.set_system_agent_config_item_enabled(
            section_id,
            item_id,
            payload.enabled,
            session,
        )
        await session.commit()
        return agent_config_out(config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/system-agent-config/{section_id}/{item_id:path}", response_model=AgentConfigOut)
async def delete_system_agent_config_item(
    section_id: str,
    item_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        config = await system_config_service.delete_system_agent_config_item(
            section_id,
            item_id,
            session,
        )
        await session.commit()
        return agent_config_out(config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/system-agent-config/{section_id}/{item_id:path}/reset", response_model=AgentConfigOut)
async def reset_system_agent_config_item(
    section_id: str,
    item_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        config = await system_config_service.reset_system_agent_config_item(
            section_id,
            item_id,
            session,
        )
        await session.commit()
        return agent_config_out(config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/system-agent-config/mcp", response_model=AgentConfigOut)
async def upsert_system_mcp_server(
    payload: SystemMcpServerUpsertIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        config = await system_config_service.upsert_system_mcp_server(
            payload.id,
            payload.server,
            enabled=payload.enabled,
            session=session,
        )
        await session.commit()
        return agent_config_out(config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/system-agent-config/skills/{skill_id}", response_model=AgentConfigOut)
async def upload_system_skill(
    request: Request,
    skill_id: str,
    enabled: bool = True,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        config = await system_config_service.install_system_skill_from_zip(
            skill_id,
            await request.body(),
            enabled=enabled,
            session=session,
        )
        await session.commit()
        return agent_config_out(config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/system-agent-config/skills/{skill_id}/download")
async def download_system_skill(
    skill_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        archive = await system_config_service.system_skill_zip_bytes(skill_id, session)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{skill_id}.zip"'},
    )


@router.post("/clients/{client_id}/agent-profiles", response_model=AgentProfileOut)
async def create_client_agent_profile(
    request: Request,
    client_id: UUID,
    payload: AgentProfileCreateIn,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).create_profile(payload, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.post("/agent-profiles", response_model=AgentProfileOut)
async def create_agent_profile(
    request: Request,
    payload: AgentProfileCreateIn,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).create_profile(payload)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get("/clients/{client_id}/agent-profiles/detail", response_model=AgentProfileOut)
async def read_client_agent_profile_by_id(
    request: Request,
    client_id: UUID,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).get_profile(profile_id, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get("/agent-profiles/detail", response_model=AgentProfileOut)
async def read_agent_profile_by_id(
    request: Request,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).get_profile(profile_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch("/clients/{client_id}/agent-profiles/detail", response_model=AgentProfileOut)
async def update_client_agent_profile_by_id(
    request: Request,
    client_id: UUID,
    payload: AgentProfileUpdateIn,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).update_profile(
            profile_id,
            AgentProfileUpdate.from_payload(payload),
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch("/agent-profiles/detail", response_model=AgentProfileOut)
async def update_agent_profile_by_id(
    request: Request,
    payload: AgentProfileUpdateIn,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).update_profile(
            profile_id,
            AgentProfileUpdate.from_payload(payload),
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.delete("/clients/{client_id}/agent-profiles/detail", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_agent_profile_by_id(
    request: Request,
    client_id: UUID,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await _service(request, session).delete_profile(profile_id, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/agent-profiles/detail", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_profile_by_id(
    request: Request,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await _service(request, session).delete_profile(profile_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/clients/{client_id}/agent-profiles/{profile_id}", response_model=AgentProfileOut)
async def read_client_agent_profile(
    request: Request,
    client_id: UUID,
    profile_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).get_profile(profile_id, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get("/agent-profiles/{profile_id}", response_model=AgentProfileOut)
async def read_agent_profile(
    request: Request,
    profile_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).get_profile(profile_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch("/clients/{client_id}/agent-profiles/{profile_id}", response_model=AgentProfileOut)
async def update_client_agent_profile(
    request: Request,
    client_id: UUID,
    profile_id: str,
    payload: AgentProfileUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).update_profile(
            profile_id,
            AgentProfileUpdate.from_payload(payload),
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch("/agent-profiles/{profile_id}", response_model=AgentProfileOut)
async def update_agent_profile(
    request: Request,
    profile_id: str,
    payload: AgentProfileUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> AgentProfileOut:
    try:
        return await _service(request, session).update_profile(
            profile_id,
            AgentProfileUpdate.from_payload(payload),
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.delete("/clients/{client_id}/agent-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_agent_profile(
    request: Request,
    client_id: UUID,
    profile_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await _service(request, session).delete_profile(profile_id, client_id=client_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/agent-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_profile(
    request: Request,
    profile_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await _service(request, session).delete_profile(profile_id)
    except AgentProfileApiError as exc:
        _raise_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/clients/{client_id}/agent-profile-config",
    response_model=AgentConfigOut,
)
async def read_agent_profile_config_by_id(
    request: Request,
    client_id: UUID,
    agent: str,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        return await _service(request, session).get_profile_config(
            profile_id,
            agent,
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/agent-profiles/{profile_id}/agent-config/{agent}",
    response_model=AgentConfigOut,
)
async def read_agent_profile_config(
    request: Request,
    client_id: UUID,
    profile_id: str,
    agent: str,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        return await _service(request, session).get_profile_config(
            profile_id,
            agent,
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch(
    "/clients/{client_id}/agent-profile-config/{agent}/{section_id}/{item_id:path}",
    response_model=AgentConfigOut,
)
async def update_agent_profile_config_item_by_id(
    request: Request,
    client_id: UUID,
    agent: str,
    section_id: str,
    item_id: str,
    payload: AgentConfigToggleIn,
    profile_id: str = ProfileIdQuery,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        return await _service(request, session).set_profile_config_item_enabled(
            profile_id,
            agent,
            section_id,
            item_id,
            payload.enabled,
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch(
    "/clients/{client_id}/agent-profiles/{profile_id}/agent-config/{agent}/{section_id}/{item_id:path}",
    response_model=AgentConfigOut,
)
async def update_agent_profile_config_item(
    request: Request,
    client_id: UUID,
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    payload: AgentConfigToggleIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        return await _service(request, session).set_profile_config_item_enabled(
            profile_id,
            agent,
            section_id,
            item_id,
            payload.enabled,
            client_id=client_id,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)


@router.patch(
    "/agent-profiles/{profile_id}/agent-config/{agent}/{section_id}/{item_id:path}",
    response_model=AgentConfigOut,
)
async def update_local_agent_profile_config_item(
    request: Request,
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    payload: AgentConfigToggleIn,
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    try:
        return await _service(request, session).set_profile_config_item_enabled(
            profile_id,
            agent,
            section_id,
            item_id,
            payload.enabled,
        )
    except AgentProfileApiError as exc:
        _raise_http(exc)
