from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.platform.ui_events import ui_event_hub_from_state
from app.contexts.terminal_artifacts.api.schemas import (
    ProjectArtifactListOut,
    TerminalArtifactCreateIn,
    TerminalArtifactListOut,
    TerminalArtifactOut,
)
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_artifacts.application import schedule_terminal_artifact_generation
from app.contexts.terminal_artifacts.application.api_service import (
    TerminalArtifactApiError,
    TerminalArtifactApiService,
    TerminalArtifactRuntimeDeps,
)
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager, get_tmux_manager
from app.platform.html_security import ARTIFACT_HTML_CSP, artifact_html_headers

router = APIRouter(prefix="/api", tags=["terminal-artifacts"])
ArtifactLimit = Annotated[int, Query(ge=1, le=100)]
ArtifactOffset = Annotated[int, Query(ge=0)]
ArtifactScope = Annotated[Literal["terminal", "project"], Query()]
ProjectPath = Annotated[str | None, Query(min_length=1, max_length=4096)]

def _service(session: AsyncSession) -> TerminalArtifactApiService:
    return TerminalArtifactApiService(session)


def _client_connection_registry(request: Request) -> ClientConnectionRegistry:
    registry = getattr(request.app.state, "client_connections", None)
    if registry is None:
        registry = ClientConnectionRegistry()
        request.app.state.client_connections = registry
    return registry


def _terminal_broker(request: Request) -> TerminalBroker:
    broker = getattr(request.app.state, "terminal_broker", None)
    if broker is None:
        broker = TerminalBroker()
        request.app.state.terminal_broker = broker
    return broker


def _runtime_deps(request: Request, tmux_manager: TmuxManager) -> TerminalArtifactRuntimeDeps:
    return TerminalArtifactRuntimeDeps(
        session_factory=SessionLocal,
        tmux_manager=tmux_manager,
        terminal_broker=_terminal_broker(request),
        registry=_client_connection_registry(request),
        ui_event_hub=ui_event_hub_from_state(request.app.state),
        schedule_generation=schedule_terminal_artifact_generation,
    )


def _raise_http(exc: TerminalArtifactApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get(
    "/clients/{client_id}/windows/{window_id}/artifacts",
    response_model=TerminalArtifactListOut,
)
async def list_window_artifacts(
    client_id: UUID,
    window_id: UUID,
    limit: ArtifactLimit = 50,
    offset: ArtifactOffset = 0,
    artifact_scope: ArtifactScope = "terminal",
    project_path: ProjectPath = None,
    session: AsyncSession = Depends(get_session),
) -> TerminalArtifactListOut:
    try:
        return await _service(session).list_window_artifacts(
            client_id,
            window_id,
            limit=limit,
            offset=offset,
            artifact_scope=artifact_scope,
            project_path=project_path,
        )
    except TerminalArtifactApiError as exc:
        _raise_http(exc)


@router.post(
    "/clients/{client_id}/windows/{window_id}/artifacts",
    response_model=TerminalArtifactOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_window_artifact(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    payload: TerminalArtifactCreateIn,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> TerminalArtifactOut:
    try:
        artifact = await _service(session).create_window_artifact(
            client_id,
            window_id,
            payload,
            runtime=_runtime_deps(request, tmux_manager),
        )
    except TerminalArtifactApiError as exc:
        _raise_http(exc)
    await _publish_artifact_created(request, client_id, window_id)
    return artifact


@router.get(
    "/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}",
    response_model=TerminalArtifactOut,
)
async def read_window_artifact(
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> TerminalArtifactOut:
    try:
        return await _service(session).read_window_artifact(client_id, window_id, artifact_id)
    except TerminalArtifactApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}/html",
    response_class=Response,
)
async def read_window_artifact_html(
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        html = await _service(session).read_window_artifact_html(client_id, window_id, artifact_id)
    except TerminalArtifactApiError as exc:
        _raise_http(exc)
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers=artifact_html_headers(),
    )


@router.get("/windows/{window_id}/artifacts", response_model=TerminalArtifactListOut)
async def list_local_window_artifacts(
    window_id: UUID,
    limit: ArtifactLimit = 50,
    offset: ArtifactOffset = 0,
    artifact_scope: ArtifactScope = "terminal",
    project_path: ProjectPath = None,
    session: AsyncSession = Depends(get_session),
) -> TerminalArtifactListOut:
    try:
        service = _service(session)
        client_id = await service.local_client_id()
        return await service.list_window_artifacts(
            client_id,
            window_id,
            limit=limit,
            offset=offset,
            artifact_scope=artifact_scope,
            project_path=project_path,
        )
    except TerminalArtifactApiError as exc:
        _raise_http(exc)


@router.post(
    "/windows/{window_id}/artifacts",
    response_model=TerminalArtifactOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_local_window_artifact(
    request: Request,
    window_id: UUID,
    payload: TerminalArtifactCreateIn,
    session: AsyncSession = Depends(get_session),
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> TerminalArtifactOut:
    try:
        service = _service(session)
        client_id = await service.local_client_id()
        artifact = await service.create_window_artifact(
            client_id,
            window_id,
            payload,
            runtime=_runtime_deps(request, tmux_manager),
        )
    except TerminalArtifactApiError as exc:
        _raise_http(exc)
    await _publish_artifact_created(request, client_id, window_id)
    return artifact


@router.get(
    "/clients/{client_id}/projects/artifacts",
    response_model=ProjectArtifactListOut,
)
async def list_project_artifacts(
    client_id: UUID,
    project_path: Annotated[str, Query(min_length=1, max_length=4096)],
    limit: ArtifactLimit = 50,
    offset: ArtifactOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> ProjectArtifactListOut:
    try:
        return await _service(session).list_project_artifacts(
            client_id,
            project_path,
            limit=limit,
            offset=offset,
        )
    except TerminalArtifactApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/projects/artifacts/{artifact_id}",
    response_model=TerminalArtifactOut,
)
async def read_project_artifact(
    client_id: UUID,
    artifact_id: UUID,
    project_path: Annotated[str, Query(min_length=1, max_length=4096)],
    session: AsyncSession = Depends(get_session),
) -> TerminalArtifactOut:
    try:
        return await _service(session).read_project_artifact(client_id, project_path, artifact_id)
    except TerminalArtifactApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/projects/artifacts/{artifact_id}/html",
    response_class=Response,
)
async def read_project_artifact_html(
    client_id: UUID,
    artifact_id: UUID,
    project_path: Annotated[str, Query(min_length=1, max_length=4096)],
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        html = await _service(session).read_project_artifact_html(client_id, project_path, artifact_id)
    except TerminalArtifactApiError as exc:
        _raise_http(exc)
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers=artifact_html_headers(),
    )


async def _publish_artifact_created(request: Request, client_id: UUID, window_id: UUID) -> None:
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["terminal_artifacts"],
        client_id=client_id,
        window_id=window_id,
        reason="artifact_created",
    )
