from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.models import ArtifactPluginPreviewSession, ArtifactPluginPreviewStatus
from app.platform.plugins.artifact_plugins.component_storage import components_from_parts
from app.platform.plugins.artifact_plugins.template_plugin import TemplateTerminalArtifactPlugin

PREVIEW_SESSION_TTL = timedelta(hours=24)


class ArtifactPluginPreviewError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ArtifactPluginPreviewPayload:
    title: str
    python_source: str
    prompt_template: str
    html_template: str
    json_schema: dict[str, Any]
    demo_content_json: dict[str, Any] | None


@dataclass(frozen=True)
class ArtifactPluginPreviewList:
    previews: list[ArtifactPluginPreviewSession]
    total: int


class ArtifactPluginPreviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_window_previews(
        self,
        *,
        client_id: UUID,
        window_id: UUID,
        limit: int,
        offset: int,
    ) -> ArtifactPluginPreviewList:
        await self._require_window(client_id, window_id)
        filters = (
            ArtifactPluginPreviewSession.client_id == client_id,
            ArtifactPluginPreviewSession.window_id == window_id,
            ArtifactPluginPreviewSession.expires_at > _now(),
        )
        total = await self._session.scalar(
            select(sa_func.count()).select_from(ArtifactPluginPreviewSession).where(*filters)
        )
        previews = list(
            await self._session.scalars(
                select(ArtifactPluginPreviewSession)
                .where(*filters)
                .order_by(desc(ArtifactPluginPreviewSession.updated_at), desc(ArtifactPluginPreviewSession.id))
                .offset(offset)
                .limit(limit)
            )
        )
        return ArtifactPluginPreviewList(previews=previews, total=int(total or 0))

    async def create_preview(
        self,
        *,
        client_id: UUID,
        window_id: UUID,
        created_by_window_id: UUID,
        payload: ArtifactPluginPreviewPayload,
    ) -> ArtifactPluginPreviewSession:
        return await self.upsert_preview(
            preview_id=uuid4(),
            client_id=client_id,
            window_id=window_id,
            created_by_window_id=created_by_window_id,
            payload=payload,
        )

    async def upsert_preview(
        self,
        *,
        preview_id: UUID,
        client_id: UUID,
        window_id: UUID,
        created_by_window_id: UUID,
        payload: ArtifactPluginPreviewPayload,
    ) -> ArtifactPluginPreviewSession:
        await self._require_window(client_id, window_id)
        await self._require_window(client_id, created_by_window_id)
        existing = await self._session.get(ArtifactPluginPreviewSession, preview_id)
        if existing is not None and (
            existing.client_id != client_id
            or existing.window_id != window_id
            or existing.created_by_window_id != created_by_window_id
        ):
            raise ArtifactPluginPreviewError(404, "artifact plugin preview not found")

        render = _render_preview(payload)
        values = {
            "client_id": client_id,
            "window_id": window_id,
            "created_by_window_id": created_by_window_id,
            "status": render.status,
            "draft_artifact_kind": render.draft_artifact_kind,
            "title": payload.title,
            "components_json": _components_json(payload),
            "demo_content_json": render.demo_content_json,
            "rendered_content_json": render.rendered_content_json,
            "display_html": render.display_html,
            "last_error": render.last_error,
            "expires_at": _now() + PREVIEW_SESSION_TTL,
        }
        if existing is None:
            preview = ArtifactPluginPreviewSession(id=preview_id, **values)
            self._session.add(preview)
        else:
            preview = existing
            for key, value in values.items():
                setattr(preview, key, value)
            preview.updated_at = _now()
        await self._session.commit()
        await self._session.refresh(preview)
        return preview

    async def read_preview(self, preview_id: UUID) -> ArtifactPluginPreviewSession:
        preview = await self._session.get(ArtifactPluginPreviewSession, preview_id)
        if preview is None or _is_expired(preview.expires_at):
            raise ArtifactPluginPreviewError(404, "artifact plugin preview not found")
        return preview

    async def read_preview_html(self, preview_id: UUID) -> str:
        preview = await self.read_preview(preview_id)
        if preview.display_html is None:
            raise ArtifactPluginPreviewError(404, preview.last_error or "artifact plugin preview html not ready")
        return preview.display_html

    async def delete_preview(self, preview_id: UUID) -> ArtifactPluginPreviewSession:
        preview = await self.read_preview(preview_id)
        await self._session.delete(preview)
        await self._session.commit()
        return preview

    async def _require_window(self, client_id: UUID, window_id: UUID) -> None:
        if await get_client(self._session, client_id) is None:
            raise ArtifactPluginPreviewError(404, "client not found")
        if await get_window_for_client(self._session, client_id, window_id) is None:
            raise ArtifactPluginPreviewError(404, "window not found")


@dataclass(frozen=True)
class _PreviewRender:
    status: ArtifactPluginPreviewStatus
    draft_artifact_kind: str | None
    demo_content_json: dict[str, Any] | None
    rendered_content_json: dict[str, Any] | None
    display_html: str | None
    last_error: str | None


def _render_preview(payload: ArtifactPluginPreviewPayload) -> _PreviewRender:
    draft_artifact_kind: str | None = None
    demo_content_json = payload.demo_content_json
    try:
        with tempfile.TemporaryDirectory(prefix="artifact-plugin-preview-session-") as temp_dir:
            components = components_from_parts(
                python_source=payload.python_source,
                prompt_template=payload.prompt_template,
                html_template=payload.html_template,
                json_schema=payload.json_schema,
                preview_content_json=payload.demo_content_json,
                root=Path(temp_dir),
            )
        draft_artifact_kind = components.artifact_kind
        demo_content_json = components.preview_content_json
        rendered = TemplateTerminalArtifactPlugin(components).render(demo_content_json)
        return _PreviewRender(
            status=ArtifactPluginPreviewStatus.valid,
            draft_artifact_kind=draft_artifact_kind,
            demo_content_json=demo_content_json,
            rendered_content_json=rendered.content_json,
            display_html=rendered.display_html,
            last_error=None,
        )
    except Exception as exc:
        return _PreviewRender(
            status=ArtifactPluginPreviewStatus.invalid,
            draft_artifact_kind=draft_artifact_kind,
            demo_content_json=demo_content_json,
            rendered_content_json=None,
            display_html=None,
            last_error=str(exc),
        )


def _components_json(payload: ArtifactPluginPreviewPayload) -> dict[str, Any]:
    return {
        "python_source": payload.python_source,
        "prompt_template": payload.prompt_template,
        "html_template": payload.html_template,
        "json_schema": payload.json_schema,
    }


def _now() -> datetime:
    return datetime.now(UTC)


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        return expires_at <= datetime.now()
    return expires_at <= _now()
