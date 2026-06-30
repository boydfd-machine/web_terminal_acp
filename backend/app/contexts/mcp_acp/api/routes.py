from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import McpTokenClaims, auth_enabled, verify_mcp_token
from app.contexts.terminal_runtime.application.runtime_provider import get_tmux_manager
from app.db import SessionLocal, get_session
from app.contexts.mcp_acp.application.service import McpAcpService, McpAcpServiceError
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from .schemas import (
    McpArtifactPluginPreviewOut,
    McpArtifactPluginPreviewUpsertIn,
    McpCaptureOutputIn,
    McpCaptureOutputOut,
    McpClientListOut,
    McpCreateWindowIn,
    McpProjectTodoContextOut,
    McpReadProjectTodoIn,
    McpSendInputIn,
    McpSendInputOut,
    McpWaitForOutputIn,
    McpWaitForOutputOut,
    McpWindowListOut,
    McpWindowOut,
)

router = APIRouter(prefix="/api/mcp/acp", tags=["mcp-acp"])
agent_ops_router = APIRouter(prefix="/api/agent-ops", tags=["agent-ops"])
OpsLimit = Annotated[int, Query(ge=1, le=500)]
OpsOffset = Annotated[int, Query(ge=0)]
OpsTodoSearchLimit = Annotated[int, Query(ge=1, le=50)]
OpsTodoSearchQuery = Annotated[str, Query(min_length=1, max_length=512)]
ArtifactScope = Annotated[Literal["terminal", "project"], Query()]
ProjectPath = Annotated[str | None, Query(min_length=1, max_length=4096)]


async def _require_source_ops(
    authorization: str | None = Header(default=None),
    source_client_id: UUID | None = Header(default=None, alias="X-Web-Terminal-Source-Client-Id"),
    source_window_id: UUID | None = Header(default=None, alias="X-Web-Terminal-Source-Window-Id"),
) -> McpTokenClaims:
    if auth_enabled():
        scheme, separator, token = (authorization or "").partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="source ops token required")
        claims = verify_mcp_token(token)
        if claims is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid source ops token")
        return claims

    if source_client_id is None or source_window_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="source ops headers required")
    return McpTokenClaims(
        source_client_id=source_client_id,
        source_window_id=source_window_id,
        issued_at=0,
    )


def _service(request: Request, session: AsyncSession) -> McpAcpService:
    return McpAcpService(
        session=session,
        app_state=request.app.state,
        tmux_manager=get_tmux_manager(),
        session_factory=SessionLocal,
    )


def _raise_http(exc: McpAcpServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@agent_ops_router.get("/clients", response_model=McpClientListOut)
@router.get("/clients", response_model=McpClientListOut)
async def mcp_list_clients(
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpClientListOut:
    try:
        clients = await _service(request, session).list_clients(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpClientListOut.model_validate({"clients": clients})


@agent_ops_router.get("/clients/{client_id}/windows", response_model=McpWindowListOut)
@router.get("/clients/{client_id}/windows", response_model=McpWindowListOut)
async def mcp_list_windows(
    client_id: UUID,
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpWindowListOut:
    try:
        windows = await _service(request, session).list_windows(
            client_id,
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpWindowListOut.model_validate({"windows": windows})


@agent_ops_router.post("/windows", response_model=McpWindowOut)
@router.post("/windows", response_model=McpWindowOut)
async def mcp_create_window(
    request: Request,
    payload: McpCreateWindowIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpWindowOut:
    try:
        window = await _service(request, session).create_window(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            target_client_id=payload.target_client_id,
            cwd=payload.cwd,
            shell_command=payload.shell_command,
            agent_client=payload.agent_client,
            prompt=payload.prompt,
            folder_path=payload.folder_path,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpWindowOut.model_validate(window)


@agent_ops_router.post("/windows/input", response_model=McpSendInputOut)
@router.post("/windows/input", response_model=McpSendInputOut)
async def mcp_send_input(
    request: Request,
    payload: McpSendInputIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpSendInputOut:
    try:
        await _service(request, session).send_input(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            target_client_id=payload.target_client_id,
            window_id=payload.window_id,
            text=payload.input,
            append_enter=payload.append_enter,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpSendInputOut(ok=True)


@agent_ops_router.post("/windows/capture", response_model=McpCaptureOutputOut)
@router.post("/windows/capture", response_model=McpCaptureOutputOut)
async def mcp_capture_output(
    request: Request,
    payload: McpCaptureOutputIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpCaptureOutputOut:
    try:
        capture = await _service(request, session).capture_output(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            target_client_id=payload.target_client_id,
            window_id=payload.window_id,
            history_lines=payload.history_lines,
            max_bytes=payload.max_bytes,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpCaptureOutputOut.model_validate(capture)


@agent_ops_router.post("/windows/wait-for-output", response_model=McpWaitForOutputOut)
@router.post("/windows/wait-for-output", response_model=McpWaitForOutputOut)
async def mcp_wait_for_output(
    request: Request,
    payload: McpWaitForOutputIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpWaitForOutputOut:
    try:
        capture = await _service(request, session).wait_for_output(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            target_client_id=payload.target_client_id,
            window_id=payload.window_id,
            contains=payload.contains,
            timeout_seconds=payload.timeout_seconds,
            poll_interval_seconds=payload.poll_interval_seconds,
            history_lines=payload.history_lines,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpWaitForOutputOut.model_validate(capture)


@agent_ops_router.post("/project-todos/read", response_model=McpProjectTodoContextOut)
@router.post("/project-todos/read", response_model=McpProjectTodoContextOut)
async def mcp_read_project_todo(
    request: Request,
    payload: McpReadProjectTodoIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpProjectTodoContextOut:
    try:
        context = await _service(request, session).read_project_todo(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            todo_id=payload.todo_id,
            include_agent_record=payload.include_agent_record,
            include_worktree=payload.include_worktree,
            include_related=payload.include_related,
            agent_record_message_limit=payload.agent_record_message_limit,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpProjectTodoContextOut.model_validate(context)


@agent_ops_router.get("/project-todos/search")
async def agent_ops_search_project_todos(
    request: Request,
    q: OpsTodoSearchQuery,
    project_path: ProjectPath = None,
    limit: OpsTodoSearchLimit = 25,
    offset: OpsOffset = 0,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await _service(request, session).search_project_todos(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            query=_normalized_search_query(q),
            project_path=_normalized_project_path(project_path) if project_path is not None else None,
            limit=limit,
            offset=offset,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)


@agent_ops_router.post("/artifact-plugin-previews/upsert", response_model=McpArtifactPluginPreviewOut)
@router.post("/artifact-plugin-previews/upsert", response_model=McpArtifactPluginPreviewOut)
async def mcp_upsert_artifact_plugin_preview(
    request: Request,
    payload: McpArtifactPluginPreviewUpsertIn,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> McpArtifactPluginPreviewOut:
    try:
        preview = await _service(request, session).upsert_artifact_plugin_preview(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            preview_id=payload.preview_id,
            title=payload.title,
            python_source=payload.python_source,
            prompt_template=payload.prompt_template,
            html_template=payload.html_template,
            json_schema=payload.json_schema,
            demo_content_json=payload.demo_content_json,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return McpArtifactPluginPreviewOut.model_validate(preview)


@agent_ops_router.get("/clients/{client_id}/windows/{window_id}/agent-preview")
async def agent_ops_read_agent_preview(
    client_id: UUID,
    window_id: UUID,
    request: Request,
    limit: OpsLimit = 200,
    offset: OpsOffset = 0,
    detail: bool = False,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await _service(request, session).read_agent_preview(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
            detail=detail,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)


@agent_ops_router.get("/clients/{client_id}/windows/{window_id}/artifacts")
async def agent_ops_list_artifacts(
    client_id: UUID,
    window_id: UUID,
    request: Request,
    limit: OpsLimit = 50,
    offset: OpsOffset = 0,
    artifact_scope: ArtifactScope = "terminal",
    project_path: ProjectPath = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await _service(request, session).list_artifacts(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
            artifact_scope=artifact_scope,
            project_path=project_path,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)


@agent_ops_router.get("/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}")
async def agent_ops_read_artifact(
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    request: Request,
    artifact_scope: ArtifactScope = "terminal",
    project_path: ProjectPath = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await _service(request, session).read_artifact(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            client_id=client_id,
            window_id=window_id,
            artifact_id=artifact_id,
            artifact_scope=artifact_scope,
            project_path=project_path,
            html=False,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return result if isinstance(result, dict) else {"text": result}


@agent_ops_router.get("/clients/{client_id}/windows/{window_id}/artifacts/{artifact_id}/html")
async def agent_ops_read_artifact_html(
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    request: Request,
    artifact_scope: ArtifactScope = "terminal",
    project_path: ProjectPath = None,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        result = await _service(request, session).read_artifact(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            client_id=client_id,
            window_id=window_id,
            artifact_id=artifact_id,
            artifact_scope=artifact_scope,
            project_path=project_path,
            html=True,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return _html_response(str(result))


@agent_ops_router.get("/project-todos/{todo_id}/artifacts/{artifact_ref}")
async def agent_ops_read_card_artifact(
    todo_id: UUID,
    artifact_ref: str,
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await _service(request, session).read_card_artifact(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            todo_id=todo_id,
            artifact_ref=artifact_ref,
            html=False,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return result if isinstance(result, dict) else {"text": result}


@agent_ops_router.get("/project-todos/{todo_id}/artifacts/{artifact_ref}/html")
async def agent_ops_read_card_artifact_html(
    todo_id: UUID,
    artifact_ref: str,
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        result = await _service(request, session).read_card_artifact(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            todo_id=todo_id,
            artifact_ref=artifact_ref,
            html=True,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return _html_response(str(result))


@agent_ops_router.get("/clients/{client_id}/windows/{window_id}/artifact-plugin-previews")
async def agent_ops_list_artifact_plugin_previews(
    client_id: UUID,
    window_id: UUID,
    request: Request,
    limit: OpsLimit = 50,
    offset: OpsOffset = 0,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await _service(request, session).list_artifact_plugin_previews(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)


@agent_ops_router.get("/artifact-plugin-previews/{preview_id}")
async def agent_ops_read_artifact_plugin_preview(
    preview_id: UUID,
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await _service(request, session).read_artifact_plugin_preview(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            preview_id=preview_id,
            html=False,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return result if isinstance(result, dict) else {"text": result}


@agent_ops_router.get("/artifact-plugin-previews/{preview_id}/html")
async def agent_ops_read_artifact_plugin_preview_html(
    preview_id: UUID,
    request: Request,
    source: McpTokenClaims = Depends(_require_source_ops),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        result = await _service(request, session).read_artifact_plugin_preview(
            source_client_id=source.source_client_id,
            source_window_id=source.source_window_id,
            preview_id=preview_id,
            html=True,
        )
    except McpAcpServiceError as exc:
        _raise_http(exc)
    return _html_response(str(result))


def _html_response(html: str) -> Response:
    return Response(html, media_type="text/html; charset=utf-8")


def _normalized_search_query(q: str) -> str:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="search query is required")
    return query


def _normalized_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
