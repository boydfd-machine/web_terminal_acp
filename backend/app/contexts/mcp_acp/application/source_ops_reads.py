from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contexts.terminal_artifacts.application.api_service import (
    TerminalArtifactApiError,
    TerminalArtifactApiService,
)
from app.contexts.windows.application.agent_record_projection import load_compact_agent_chat_messages
from app.contexts.workspace.application.project_todo_search import search_project_todos as search_project_todo_models
from app.models import AiSession, Event, EventSourceType
from app.platform.plugins.artifact_plugins.preview_sessions import (
    ArtifactPluginPreviewError,
    ArtifactPluginPreviewService,
)


class SourceOpsReadError(Exception):
    def __init__(self, status_code: int, detail: object) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


async def read_agent_preview(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
    detail: bool,
) -> dict[str, object]:
    if detail:
        return await _agent_preview_detail(session, client_id, window_id, limit, offset)
    messages = await load_compact_agent_chat_messages(
        session,
        client_id=client_id,
        window_id=window_id,
        message_limit=limit + offset + 1,
    )
    page = messages[offset : offset + limit]
    return {
        "window_id": str(window_id),
        "messages": [
            {
                "role": message.role,
                "body": message.body,
                "body_format": message.body_format,
                "source_id": message.source_id,
                "created_at": message.created_at,
            }
            for message in page
        ],
        "messages_total": offset + len(page) + (1 if len(messages) > offset + len(page) else 0),
        "messages_limit": limit,
        "messages_offset": offset,
        "messages_has_more": len(messages) > offset + len(page),
    }


async def search_project_todos(
    session: AsyncSession,
    *,
    client_id: UUID,
    query: str,
    project_path: str | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    result = await search_project_todo_models(
        session,
        client_id=client_id,
        query=query,
        project_path=project_path,
        limit=limit,
        offset=offset,
    )
    return result.model_dump(mode="json")


async def list_artifacts(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
    artifact_scope: str,
    project_path: str | None,
) -> dict[str, object]:
    try:
        result = await TerminalArtifactApiService(session).list_window_artifacts(
            client_id,
            window_id,
            limit=limit,
            offset=offset,
            artifact_scope=artifact_scope,
            project_path=project_path,
        )
    except TerminalArtifactApiError as exc:
        raise SourceOpsReadError(exc.status_code, exc.detail) from exc
    return result.model_dump(mode="json")


async def read_artifact(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    artifact_scope: str,
    project_path: str | None,
    html: bool,
) -> dict[str, object] | str:
    service = TerminalArtifactApiService(session)
    try:
        if artifact_scope == "project":
            if project_path is None:
                raise SourceOpsReadError(400, "project_path is required for project artifacts")
            if html:
                return await service.read_project_artifact_html(client_id, project_path, artifact_id)
            return (await service.read_project_artifact(client_id, project_path, artifact_id)).model_dump(mode="json")
        if html:
            return await service.read_window_artifact_html(client_id, window_id, artifact_id)
        return (await service.read_window_artifact(client_id, window_id, artifact_id)).model_dump(mode="json")
    except TerminalArtifactApiError as exc:
        raise SourceOpsReadError(exc.status_code, exc.detail) from exc


def card_artifact(context: dict[str, object], artifact_ref: str) -> dict[str, object]:
    artifacts = context.get("artifacts")
    if not isinstance(artifacts, list):
        raise SourceOpsReadError(404, "project todo context has no artifacts list")
    for item in artifacts:
        if isinstance(item, dict) and (item.get("id") == artifact_ref or item.get("artifact_id") == artifact_ref):
            return item
    raise SourceOpsReadError(404, f"card artifact not found: {artifact_ref}")


async def list_artifact_plugin_previews(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
) -> dict[str, object]:
    try:
        result = await ArtifactPluginPreviewService(session).list_window_previews(
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
        )
    except ArtifactPluginPreviewError as exc:
        raise SourceOpsReadError(exc.status_code, exc.detail) from exc
    return {
        "window_id": str(window_id),
        "previews": [preview_payload(preview, include_html=False) for preview in result.previews],
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(result.previews) < result.total,
    }


async def read_artifact_plugin_preview(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_window_id: UUID,
    preview_id: UUID,
    html: bool,
) -> dict[str, object] | str:
    try:
        preview = await ArtifactPluginPreviewService(session).read_preview(preview_id)
    except ArtifactPluginPreviewError as exc:
        raise SourceOpsReadError(exc.status_code, exc.detail) from exc
    if preview.client_id != client_id or (
        preview.window_id != source_window_id and preview.created_by_window_id != source_window_id
    ):
        raise SourceOpsReadError(404, "artifact plugin preview not found")
    if html:
        if preview.display_html is None:
            raise SourceOpsReadError(404, preview.last_error or "artifact plugin preview html not ready")
        return preview.display_html
    return preview_payload(preview)


async def _agent_preview_detail(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
) -> dict[str, object]:
    filters = [Event.client_id == client_id, Event.virtual_window_id == window_id, Event.kind != "terminal_output"]
    total = await session.scalar(select(func.count()).select_from(Event).where(*filters))
    sessions = list(
        await session.scalars(
            select(AiSession)
            .where(AiSession.client_id == client_id, AiSession.virtual_window_id == window_id)
            .order_by(AiSession.created_at, AiSession.id)
        )
    )
    events = list(
        await session.scalars(
            select(Event)
            .options(selectinload(Event.ai_session))
            .where(*filters)
            .order_by(Event.created_at, case((Event.source_type == EventSourceType.terminal, 1), else_=0), Event.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return {
        "window_id": str(window_id),
        "sessions": [_session_payload(item) for item in sessions],
        "events": [_event_payload(item) for item in events],
        "events_total": int(total or 0),
        "events_limit": limit,
        "events_offset": offset,
        "events_has_more": offset + len(events) < int(total or 0),
    }


def _session_payload(session: AiSession) -> dict[str, object]:
    return {
        "id": str(session.id),
        "provider": session.provider,
        "source_id": session.source_id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _event_payload(event: Event) -> dict[str, object]:
    return {
        "id": str(event.id),
        "ai_session_id": str(event.ai_session_id) if event.ai_session_id is not None else None,
        "source_type": event.source_type.value,
        "source_id": event.source_id,
        "kind": event.kind,
        "payload_json": event.payload_json,
        "created_at": event.created_at,
    }


def preview_payload(preview: object, *, include_html: bool = True) -> dict[str, object]:
    return {
        "id": str(getattr(preview, "id")),
        "client_id": str(getattr(preview, "client_id")),
        "window_id": str(getattr(preview, "window_id")),
        "created_by_window_id": str(getattr(preview, "created_by_window_id")),
        "status": getattr(preview, "status").value,
        "draft_artifact_kind": getattr(preview, "draft_artifact_kind"),
        "title": getattr(preview, "title"),
        "components_json": getattr(preview, "components_json"),
        "demo_content_json": getattr(preview, "demo_content_json"),
        "rendered_content_json": getattr(preview, "rendered_content_json"),
        "display_html": getattr(preview, "display_html") if include_html else None,
        "last_error": getattr(preview, "last_error"),
        "created_at": getattr(preview, "created_at"),
        "updated_at": getattr(preview, "updated_at"),
        "expires_at": getattr(preview, "expires_at"),
    }
