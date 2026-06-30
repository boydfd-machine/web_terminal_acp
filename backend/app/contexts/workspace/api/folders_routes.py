from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.contexts.workspace.api.schemas import (
    FolderCreateIn,
    FolderOut,
    TerminalProjectOut,
)
from app.contexts.workspace.application.folders_service import (
    FolderApiError,
    FolderApiService,
    FolderReadScope,
)
from app.contexts.activity.api.schemas import ClientWindowsActivityOut
from app.contexts.windows.api.schemas import TreeFolderOut
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api", tags=["folders"])


def _service(session: AsyncSession) -> FolderApiService:
    return FolderApiService(session, refresh_session_factory=SessionLocal)


def _raise_http(exc: FolderApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/clients/{client_id}/tree", response_model=list[TreeFolderOut], response_model_exclude_none=True)
async def get_client_tree(
    client_id: UUID,
    time_range: str | None = Query(default=None, alias="range"),
    project_path: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        return await _service(session).get_tree(
            FolderReadScope.client_tree(
                client_id=client_id,
                time_range=time_range,
                project_path=project_path,
            )
        )
    except FolderApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/terminal-projects",
    response_model=list[TerminalProjectOut],
    response_model_exclude_none=True,
)
async def get_client_terminal_projects(
    client_id: UUID,
    time_range: str | None = Query(default=None, alias="range"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        return await _service(session).get_terminal_projects(
            FolderReadScope.client_terminal_projects(
                client_id=client_id,
                time_range=time_range,
            )
        )
    except FolderApiError as exc:
        _raise_http(exc)


@router.get(
    "/clients/{client_id}/windows/activity",
    response_model=ClientWindowsActivityOut,
    response_model_exclude_none=True,
)
async def get_client_windows_activity(
    client_id: UUID,
    include_runtime_tags: bool = Query(default=False),
    time_range: str | None = Query(default=None, alias="range"),
    project_path: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        return await _service(session).get_windows_activity(
            FolderReadScope.client_activity(
                client_id=client_id,
                time_range=time_range,
                project_path=project_path,
            ),
            include_runtime_tags=include_runtime_tags,
        )
    except FolderApiError as exc:
        _raise_http(exc)


@router.get("/tree", response_model=list[TreeFolderOut], response_model_exclude_none=True)
async def get_tree(
    time_range: str | None = Query(default=None, alias="range"),
    project_path: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        return await _service(session).get_local_tree(
            time_range=time_range,
            project_path=project_path,
        )
    except FolderApiError as exc:
        _raise_http(exc)


@router.post("/clients/{client_id}/folders", response_model=FolderOut)
async def create_client_folder(
    request: Request,
    client_id: UUID,
    payload: FolderCreateIn,
    session: AsyncSession = Depends(get_session),
) -> FolderOut:
    try:
        folder = await _service(session).create_folder_for_client(client_id, payload.path)
    except FolderApiError as exc:
        _raise_http(exc)
    await _publish_folder_created(request, client_id)
    return folder


@router.post("/folders", response_model=FolderOut)
async def create_folder(
    request: Request,
    payload: FolderCreateIn,
    session: AsyncSession = Depends(get_session),
) -> FolderOut:
    try:
        client_id, folder = await _service(session).create_local_folder(payload.path)
    except FolderApiError as exc:
        _raise_http(exc)
    await _publish_folder_created(request, client_id)
    return folder


async def _publish_folder_created(request: Request, client_id: UUID) -> None:
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree"],
        client_id=client_id,
        reason="folder_created",
    )
