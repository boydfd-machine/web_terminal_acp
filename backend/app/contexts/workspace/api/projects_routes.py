from __future__ import annotations

import base64
import binascii
import mimetypes
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.db import get_session
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.schemas import (
    ProjectBrowseRootListOut,
    ProjectFileContentOut,
    ProjectFileEntryOut,
    ProjectFileListOut,
    ProjectFileSaveIn,
    ProjectFileUploadIn,
    ProjectFileUploadOut,
    ProjectOut,
)
from app.contexts.workspace.application.project_browse_roots import (
    project_browse_root_options,
    resolve_project_browse_path,
)
from app.contexts.workspace.application.project_files import (
    ProjectPathError,
    relative_path_from_project,
    resolve_project_relative_path,
)
from app.contexts.workspace.application.project_agent_preferences import (
    project_agent_preference_values,
    project_agent_preferences_by_path,
)
from app.contexts.workspace.application.project_queries import (
    list_project_summaries,
    list_terminal_projects,
)
from app.models import Client, ClientRuntime
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError
from app.contexts.terminal_runtime.application.runtime_provider import get_tmux_manager
from app.contexts.activity.application.terminal_time_ranges import terminal_visible_since
from app.platform.polling_response_cache import (
    begin_response_cache_build,
    cached_or_stale_json_response_async,
    finish_response_cache_build,
    response_cache_scope,
    store_json_response_async,
)

router = APIRouter(prefix="/api/clients/{client_id}/projects", tags=["projects"])

ProjectPathQuery = Query(..., min_length=1, max_length=4096)
ProjectBrowseRootQuery = Query(None, max_length=4096)
ProjectFilePathQuery = Query("", max_length=4096)
ProjectRangeQuery = Query("7d")
PROJECT_FILE_PREVIEW_BYTES = 2 * 1024 * 1024
PROJECT_FILE_DOWNLOAD_BYTES = 50 * 1024 * 1024
PROJECT_FILE_UPLOAD_BYTES = 20 * 1024 * 1024
PROJECT_FILE_SAVE_BYTES = 2 * 1024 * 1024
TEXT_PREVIEW_ALLOWED_CONTROLS = {7, 8, 9, 10, 12, 13, 27}


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


def _broker_for_client(request: Request, client: Client) -> TerminalBroker:
    broker = getattr(request.app.state, "terminal_broker", None)
    if broker is None:
        broker = TerminalBroker()
        request.app.state.terminal_broker = broker
    if client.runtime is ClientRuntime.local:
        if broker.runtime_for(client.id) is None:
            local_runtime = getattr(request.app.state, "local_terminal_runtime", None)
            if local_runtime is None:
                from app.db import SessionLocal

                local_runtime = create_local_terminal_runtime(
                    get_tmux_manager(),
                    session_factory=SessionLocal,
                )
                request.app.state.local_terminal_runtime = local_runtime
            broker.register_runtime(client.id, local_runtime)
    else:
        if broker.runtime_for(client.id) is None:
            registry = getattr(request.app.state, "client_connections", None)
            if registry is None:
                registry = ClientConnectionRegistry()
                request.app.state.client_connections = registry
            broker.register_runtime(
                client.id,
                RemoteRuntime(client_id=client.id, registry=registry),
            )
    return broker


def _visible_since(range_value: str) -> datetime | None:
    return terminal_visible_since(range_value, now=datetime.now(UTC))


async def _list_project_out(
    session: AsyncSession,
    client_id: UUID,
    *,
    range_value: str,
) -> list[ProjectOut]:
    projects = await list_terminal_projects(
        session,
        client_id,
        visible_since=_visible_since(range_value),
    )
    summaries = {
        summary.project_path: summary
        for summary in await list_project_summaries(session, client_id)
    }
    preferences = await project_agent_preferences_by_path(
        session,
        client_id,
        [project.project_path for project in projects],
    )
    result: list[ProjectOut] = []
    for project in projects:
        summary = summaries.get(project.project_path)
        result.append(ProjectOut(
            client_id=client_id,
            path=project.project_path,
            display_name=summary.display_name if summary is not None else None,
            summary_status=summary.status.value if summary is not None else None,
            summary_updated_at=summary.updated_at if summary is not None else None,
            window_count=project.window_count,
            agent_preference=project_agent_preference_values(preferences.get(project.project_path)),
        ))
    return result


async def _cached_list_project_response(
    session: AsyncSession,
    client_id: UUID,
    *,
    range_value: str,
) -> Response:
    cache_key = (
        "projects",
        response_cache_scope(session),
        client_id,
        range_value,
    )
    cached = await cached_or_stale_json_response_async(cache_key)
    if cached is not None and not cached.expired:
        return cached.response

    active_build = begin_response_cache_build(cache_key)
    if active_build is not None:
        await active_build
        cached = await cached_or_stale_json_response_async(cache_key)
        if cached is not None:
            return cached.response

    error: BaseException | None = None
    try:
        projects = await _list_project_out(session, client_id, range_value=range_value)
        return await store_json_response_async(
            cache_key,
            projects,
            resources={"tree", "project-agent-preferences"},
            client_id=client_id,
        )
    except BaseException as exc:
        error = exc
        raise
    finally:
        finish_response_cache_build(cache_key, error)


async def _require_project_out(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    range_value: str,
) -> ProjectOut:
    normalized_path = resolve_project_relative_path(project_path).project_path
    for project in await _list_project_out(session, client_id, range_value=range_value):
        if project.path == normalized_path:
            return project
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")


def _project_path_error(exc: ProjectPathError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _runtime_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RemoteClientUnavailable):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "remote client unavailable", "reason": exc.reason},
        )
    if isinstance(exc, RemoteTerminalError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _decode_text_preview(data: bytes) -> str:
    if _looks_binary(data):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="binary file preview is unsupported")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="file is not valid utf-8") from exc


def _looks_binary(data: bytes) -> bool:
    if not data:
        return False
    control_bytes = 0
    for value in data:
        if value == 0:
            return True
        if value < 32 and value not in TEXT_PREVIEW_ALLOWED_CONTROLS:
            control_bytes += 1
    return control_bytes / len(data) > 0.30


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    client_id: UUID,
    range: str = ProjectRangeQuery,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await _require_client(session, client_id)
    return await _cached_list_project_response(session, client_id, range_value=range)


@router.get("/detail", response_model=ProjectOut)
async def get_project(
    client_id: UUID,
    project_path: str = ProjectPathQuery,
    range: str = ProjectRangeQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    await _require_client(session, client_id)
    try:
        return await _require_project_out(session, client_id, project_path, range_value=range)
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc


@router.get("/browse-roots", response_model=ProjectBrowseRootListOut)
async def list_project_browse_roots(
    client_id: UUID,
    project_path: str = ProjectPathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectBrowseRootListOut:
    await _require_client(session, client_id)
    try:
        return await project_browse_root_options(session, client_id, project_path)
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc


@router.get("/files", response_model=ProjectFileListOut)
async def list_project_files(
    client_id: UUID,
    request: Request,
    project_path: str = ProjectPathQuery,
    browse_root: str | None = ProjectBrowseRootQuery,
    path: str = ProjectFilePathQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectFileListOut:
    client = await _require_client(session, client_id)
    try:
        resolved = await resolve_project_browse_path(
            session,
            client_id,
            project_path=project_path,
            path=path,
            browse_root=browse_root,
        )
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc

    broker = _broker_for_client(request, client)
    try:
        entries = await broker.list_file_entries(client_id, resolved.absolute_path)
    except Exception as exc:
        raise _runtime_error(exc) from exc

    return ProjectFileListOut(
        project_path=resolved.project_path,
        path=resolved.relative_path,
        entries=[
            ProjectFileEntryOut(
                name=entry.name,
                path=relative_path_from_project(resolved.browse_root, entry.path),
                kind=entry.kind,
                size=entry.size,
                mtime=entry.mtime,
            )
            for entry in entries
        ],
    )


@router.get("/files/content", response_model=ProjectFileContentOut)
async def read_project_file_content(
    client_id: UUID,
    request: Request,
    project_path: str = ProjectPathQuery,
    browse_root: str | None = ProjectBrowseRootQuery,
    path: str = Query(..., min_length=1, max_length=4096),
    session: AsyncSession = Depends(get_session),
) -> ProjectFileContentOut:
    client = await _require_client(session, client_id)
    try:
        resolved = await resolve_project_browse_path(
            session,
            client_id,
            project_path=project_path,
            path=path,
            browse_root=browse_root,
        )
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc

    broker = _broker_for_client(request, client)
    try:
        data = await broker.read_file_bytes(
            client_id,
            resolved.absolute_path,
            max_bytes=PROJECT_FILE_PREVIEW_BYTES,
        )
    except Exception as exc:
        raise _runtime_error(exc) from exc

    truncated = len(data) > PROJECT_FILE_PREVIEW_BYTES
    if truncated:
        data = data[:PROJECT_FILE_PREVIEW_BYTES]
    content = _decode_text_preview(data)
    return ProjectFileContentOut(
        project_path=resolved.project_path,
        path=resolved.relative_path,
        content=content,
        encoding="utf-8",
        truncated=truncated,
        size=None if truncated else len(data),
    )


@router.get("/files/download")
async def download_project_file(
    client_id: UUID,
    request: Request,
    project_path: str = ProjectPathQuery,
    browse_root: str | None = ProjectBrowseRootQuery,
    path: str = Query(..., min_length=1, max_length=4096),
    session: AsyncSession = Depends(get_session),
) -> Response:
    client = await _require_client(session, client_id)
    try:
        resolved = await resolve_project_browse_path(
            session,
            client_id,
            project_path=project_path,
            path=path,
            browse_root=browse_root,
        )
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc

    broker = _broker_for_client(request, client)
    try:
        data = await broker.read_file_bytes(
            client_id,
            resolved.absolute_path,
            max_bytes=PROJECT_FILE_DOWNLOAD_BYTES,
        )
    except Exception as exc:
        raise _runtime_error(exc) from exc
    if len(data) > PROJECT_FILE_DOWNLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large")

    filename = resolved.relative_path.rsplit("/", 1)[-1] or "download"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/files/content", response_model=ProjectFileUploadOut)
async def save_project_file_content(
    client_id: UUID,
    payload: ProjectFileSaveIn,
    request: Request,
    project_path: str = ProjectPathQuery,
    browse_root: str | None = ProjectBrowseRootQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectFileUploadOut:
    client = await _require_client(session, client_id)
    try:
        resolved = await resolve_project_browse_path(
            session,
            client_id,
            project_path=project_path,
            path=payload.path,
            browse_root=browse_root,
        )
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc

    data = payload.content.encode("utf-8")
    if len(data) > PROJECT_FILE_SAVE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large")

    broker = _broker_for_client(request, client)
    try:
        await broker.write_file_bytes(
            client_id,
            resolved.absolute_path,
            data,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        raise _runtime_error(exc) from exc

    return ProjectFileUploadOut(
        project_path=resolved.project_path,
        path=resolved.relative_path,
        size=len(data),
    )


@router.post("/files/upload", response_model=ProjectFileUploadOut)
async def upload_project_file(
    client_id: UUID,
    payload: ProjectFileUploadIn,
    request: Request,
    project_path: str = ProjectPathQuery,
    browse_root: str | None = ProjectBrowseRootQuery,
    session: AsyncSession = Depends(get_session),
) -> ProjectFileUploadOut:
    client = await _require_client(session, client_id)
    try:
        resolved = await resolve_project_browse_path(
            session,
            client_id,
            project_path=project_path,
            path=payload.path,
            browse_root=browse_root,
        )
    except ProjectPathError as exc:
        raise _project_path_error(exc) from exc

    try:
        data = base64.b64decode(payload.content_base64.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid base64 content") from exc
    if len(data) > PROJECT_FILE_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large")

    broker = _broker_for_client(request, client)
    try:
        await broker.write_file_bytes(
            client_id,
            resolved.absolute_path,
            data,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        raise _runtime_error(exc) from exc

    return ProjectFileUploadOut(
        project_path=resolved.project_path,
        path=resolved.relative_path,
        size=len(data),
    )
