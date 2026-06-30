from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.mcp_acp.application import source_ops_reads
from app.contexts.mcp_acp.application.errors import McpAcpServiceError
from app.contexts.mcp_acp.application.source_client_scope import require_source_scope
from app.contexts.workspace.application.project_todo_context import project_todo_context_by_id
from app.platform.plugins.artifact_plugins.preview_sessions import (
    ArtifactPluginPreviewError,
    ArtifactPluginPreviewPayload,
    ArtifactPluginPreviewService,
)
from app.platform.ui_events import ui_event_hub_from_state


class McpSourceOpsMixin:
    async def read_project_todo(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        todo_id: UUID,
        include_agent_record: bool,
        include_worktree: bool,
        include_related: bool,
        agent_record_message_limit: int,
    ) -> dict[str, object]:
        await require_source_scope(self._session, source_client_id, source_window_id)
        context = await project_todo_context_by_id(
            self._session,
            todo_id,
            client_id=source_client_id,
            include_agent_record=include_agent_record,
            include_worktree=include_worktree,
            include_related=include_related,
            agent_record_message_limit=agent_record_message_limit,
        )
        if context is None:
            raise McpAcpServiceError(404, "todo not found")
        return context

    async def search_project_todos(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        query: str,
        project_path: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        await require_source_scope(self._session, source_client_id, source_window_id)
        return await source_ops_reads.search_project_todos(
            self._session,
            client_id=source_client_id,
            query=query,
            project_path=project_path,
            limit=limit,
            offset=offset,
        )

    async def read_agent_preview(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        client_id: UUID,
        window_id: UUID,
        limit: int,
        offset: int,
        detail: bool,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        await scope.require_client(self._session, client_id)
        await self._require_window(client_id, window_id)
        return await source_ops_reads.read_agent_preview(
            self._session,
            client_id=client_id,
            window_id=window_id,
            limit=limit,
            offset=offset,
            detail=detail,
        )

    async def list_artifacts(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        client_id: UUID,
        window_id: UUID,
        limit: int,
        offset: int,
        artifact_scope: str,
        project_path: str | None,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        await scope.require_client(self._session, client_id)
        try:
            return await source_ops_reads.list_artifacts(
                self._session,
                client_id=client_id,
                window_id=window_id,
                limit=limit,
                offset=offset,
                artifact_scope=artifact_scope,
                project_path=project_path,
            )
        except source_ops_reads.SourceOpsReadError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc

    async def read_artifact(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        client_id: UUID,
        window_id: UUID,
        artifact_id: UUID,
        artifact_scope: str,
        project_path: str | None,
        html: bool,
    ) -> dict[str, object] | str:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        await scope.require_client(self._session, client_id)
        try:
            return await source_ops_reads.read_artifact(
                self._session,
                client_id=client_id,
                window_id=window_id,
                artifact_id=artifact_id,
                artifact_scope=artifact_scope,
                project_path=project_path,
                html=html,
            )
        except source_ops_reads.SourceOpsReadError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc

    async def read_card_artifact(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        todo_id: UUID,
        artifact_ref: str,
        html: bool,
    ) -> dict[str, object] | str:
        context = await self.read_project_todo(
            source_client_id=source_client_id,
            source_window_id=source_window_id,
            todo_id=todo_id,
            include_agent_record=False,
            include_worktree=False,
            include_related=True,
            agent_record_message_limit=1,
        )
        try:
            artifact = source_ops_reads.card_artifact(context, artifact_ref)
        except source_ops_reads.SourceOpsReadError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc
        return await self.read_artifact(
            source_client_id=source_client_id,
            source_window_id=source_window_id,
            client_id=UUID(str(artifact["client_id"])),
            window_id=UUID(str(artifact["window_id"])),
            artifact_id=UUID(str(artifact["artifact_id"])),
            artifact_scope=str(artifact.get("artifact_scope") or "terminal"),
            project_path=artifact.get("project_path") if isinstance(artifact.get("project_path"), str) else None,
            html=html,
        )

    async def upsert_artifact_plugin_preview(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        preview_id: UUID | None,
        title: str,
        python_source: str,
        prompt_template: str,
        html_template: str,
        json_schema: dict[str, object],
        demo_content_json: dict[str, object] | None,
    ) -> dict[str, object]:
        await require_source_scope(self._session, source_client_id, source_window_id)
        try:
            preview = await ArtifactPluginPreviewService(self._session).upsert_preview(
                preview_id=preview_id or uuid4(),
                client_id=source_client_id,
                window_id=source_window_id,
                created_by_window_id=source_window_id,
                payload=ArtifactPluginPreviewPayload(
                    title=title,
                    python_source=python_source,
                    prompt_template=prompt_template,
                    html_template=html_template,
                    json_schema=dict(json_schema),
                    demo_content_json=dict(demo_content_json) if demo_content_json is not None else None,
                ),
            )
        except ArtifactPluginPreviewError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc
        await ui_event_hub_from_state(self._app_state).publish_invalidation(
            ["artifact_plugin_previews"],
            client_id=source_client_id,
            window_id=source_window_id,
            reason="mcp_preview_upserted",
        )
        return source_ops_reads.preview_payload(preview, include_html=False)

    async def list_artifact_plugin_previews(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        client_id: UUID,
        window_id: UUID,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        scope = await require_source_scope(
            self._session,
            source_client_id,
            source_window_id,
        )
        await scope.require_client(self._session, client_id)
        try:
            return await source_ops_reads.list_artifact_plugin_previews(
                self._session,
                client_id=client_id,
                window_id=window_id,
                limit=limit,
                offset=offset,
            )
        except source_ops_reads.SourceOpsReadError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc

    async def read_artifact_plugin_preview(
        self,
        *,
        source_client_id: UUID,
        source_window_id: UUID,
        preview_id: UUID,
        html: bool,
    ) -> dict[str, object] | str:
        await require_source_scope(self._session, source_client_id, source_window_id)
        try:
            return await source_ops_reads.read_artifact_plugin_preview(
                self._session,
                client_id=source_client_id,
                source_window_id=source_window_id,
                preview_id=preview_id,
                html=html,
            )
        except source_ops_reads.SourceOpsReadError as exc:
            raise McpAcpServiceError(exc.status_code, exc.detail) from exc
