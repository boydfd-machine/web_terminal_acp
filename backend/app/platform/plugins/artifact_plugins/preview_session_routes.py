from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.platform.html_security import artifact_html_headers
from app.platform.plugins.artifact_plugins.preview_sessions import (
    ArtifactPluginPreviewError,
    ArtifactPluginPreviewPayload,
    ArtifactPluginPreviewService,
)
from app.platform.plugins.artifact_plugins.schemas import (
    ArtifactPluginPreviewListOut,
    ArtifactPluginPreviewOut,
    ArtifactPluginPreviewUpsertIn,
)
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api", tags=["artifact-plugin-previews"])
PreviewLimit = Annotated[int, Query(ge=1, le=100)]
PreviewOffset = Annotated[int, Query(ge=0)]


@router.get(
    "/clients/{client_id}/windows/{window_id}/artifact-plugin-previews",
    response_model=ArtifactPluginPreviewListOut,
)
async def list_window_artifact_plugin_previews(
    client_id: UUID,
    window_id: UUID,
    limit: PreviewLimit = 50,
    offset: PreviewOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginPreviewListOut:
    try:
        result = await ArtifactPluginPreviewService(session).list_window_previews(
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
        )
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    return ArtifactPluginPreviewListOut(
        window_id=window_id,
        previews=[_preview_out(preview, include_display_html=False) for preview in result.previews],
        total=result.total,
        limit=limit,
        offset=offset,
        has_more=offset + len(result.previews) < result.total,
    )


@router.post(
    "/artifact-plugin-previews",
    response_model=ArtifactPluginPreviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_artifact_plugin_preview(
    payload: ArtifactPluginPreviewUpsertIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginPreviewOut:
    try:
        preview = await ArtifactPluginPreviewService(session).create_preview(
            client_id=payload.client_id,
            window_id=payload.window_id,
            created_by_window_id=payload.window_id,
            payload=_preview_payload(payload),
        )
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    await _publish_preview_invalidation(request, preview.client_id, preview.window_id, "preview_created")
    return _preview_out(preview, include_display_html=False)


@router.put(
    "/artifact-plugin-previews/{preview_id}",
    response_model=ArtifactPluginPreviewOut,
)
async def update_artifact_plugin_preview(
    preview_id: UUID,
    payload: ArtifactPluginPreviewUpsertIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginPreviewOut:
    try:
        preview = await ArtifactPluginPreviewService(session).upsert_preview(
            preview_id=preview_id,
            client_id=payload.client_id,
            window_id=payload.window_id,
            created_by_window_id=payload.window_id,
            payload=_preview_payload(payload),
        )
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    await _publish_preview_invalidation(request, preview.client_id, preview.window_id, "preview_updated")
    return _preview_out(preview, include_display_html=False)


@router.get(
    "/artifact-plugin-previews/{preview_id}",
    response_model=ArtifactPluginPreviewOut,
)
async def read_artifact_plugin_preview(
    preview_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginPreviewOut:
    try:
        preview = await ArtifactPluginPreviewService(session).read_preview(preview_id)
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    return _preview_out(preview)


@router.get("/artifact-plugin-previews/{preview_id}/html", response_class=Response)
async def read_artifact_plugin_preview_html(
    preview_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        html = await ArtifactPluginPreviewService(session).read_preview_html(preview_id)
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    return _html_response(html)


@router.delete("/artifact-plugin-previews/{preview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact_plugin_preview(
    preview_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        preview = await ArtifactPluginPreviewService(session).delete_preview(preview_id)
    except ArtifactPluginPreviewError as exc:
        _raise_http(exc)
    await _publish_preview_invalidation(request, preview.client_id, preview.window_id, "preview_deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _preview_payload(payload: ArtifactPluginPreviewUpsertIn) -> ArtifactPluginPreviewPayload:
    return ArtifactPluginPreviewPayload(
        title=payload.title,
        python_source=payload.python_source,
        prompt_template=payload.prompt_template,
        html_template=payload.html_template,
        json_schema=payload.json_schema,
        demo_content_json=payload.demo_content_json,
    )


def _preview_out(preview: object, *, include_display_html: bool = True) -> ArtifactPluginPreviewOut:
    return ArtifactPluginPreviewOut(
        id=getattr(preview, "id"),
        client_id=getattr(preview, "client_id"),
        window_id=getattr(preview, "window_id"),
        created_by_window_id=getattr(preview, "created_by_window_id"),
        status=getattr(preview, "status").value,
        draft_artifact_kind=getattr(preview, "draft_artifact_kind"),
        title=getattr(preview, "title"),
        components_json=getattr(preview, "components_json"),
        demo_content_json=getattr(preview, "demo_content_json"),
        rendered_content_json=getattr(preview, "rendered_content_json"),
        display_html=getattr(preview, "display_html") if include_display_html else None,
        last_error=getattr(preview, "last_error"),
        created_at=getattr(preview, "created_at"),
        updated_at=getattr(preview, "updated_at"),
        expires_at=getattr(preview, "expires_at"),
    )


def _html_response(html: str) -> Response:
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers=artifact_html_headers(),
    )


def _raise_http(exc: ArtifactPluginPreviewError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def _publish_preview_invalidation(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    reason: str,
) -> None:
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["artifact_plugin_previews"],
        client_id=client_id,
        window_id=window_id,
        reason=reason,
    )
