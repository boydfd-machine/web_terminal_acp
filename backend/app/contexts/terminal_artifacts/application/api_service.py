from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.platform.plugins.artifact_plugins import get_artifact_plugin_registry_for_scope
from app.platform.plugins.artifact_plugins.user_settings_repository import (
    restore_artifact_plugin_files_to_disk,
)
from app.config import get_settings
from app.contexts.terminal_artifacts.domain import TerminalArtifactDraft
from app.models import Client, TerminalArtifact
from app.contexts.clients.application.client_lookup import ensure_local_client, get_client
from app.contexts.terminal_artifacts.infrastructure.repository import (
    create_terminal_artifact,
    get_project_artifact_for_client,
    get_terminal_artifact_for_client,
    list_project_artifacts,
    list_terminal_artifacts_for_window,
)
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.contexts.terminal_artifacts.api.schemas import (
    ProjectArtifactListOut,
    TerminalArtifactCreateIn,
    TerminalArtifactListOut,
    TerminalArtifactOut,
)
from app.contexts.terminal_artifacts.api.projection import (
    project_artifact_list_out,
    terminal_artifact_list_out,
    terminal_artifact_out,
)
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_artifacts.application import (
    TerminalArtifactGenerationRequest,
    schedule_terminal_artifact_generation,
)
from app.contexts.terminal_artifacts.application.model_selection import (
    metadata_with_artifact_model_selection,
)
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.platform.ui_events import UiEventHub


class TerminalArtifactApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class TerminalArtifactRuntimeDeps:
    session_factory: async_sessionmaker[AsyncSession]
    tmux_manager: TmuxManager
    terminal_broker: TerminalBroker
    registry: ClientConnectionRegistry
    ui_event_hub: UiEventHub
    schedule_generation: Callable[..., None] = schedule_terminal_artifact_generation


class TerminalArtifactApiService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_window_artifacts(
        self,
        client_id: UUID,
        window_id: UUID,
        *,
        limit: int,
        offset: int,
        artifact_scope: str = "terminal",
        project_path: str | None = None,
    ) -> TerminalArtifactListOut:
        await self._require_window(client_id, window_id)
        if artifact_scope == "project":
            if project_path is None:
                raise TerminalArtifactApiError(400, "project_path is required for project artifacts")
            artifacts, total = await list_project_artifacts(
                self._session,
                client_id,
                project_path,
                limit=limit,
                offset=offset,
            )
        else:
            artifacts, total = await list_terminal_artifacts_for_window(
                self._session,
                client_id,
                window_id,
                limit=limit,
                offset=offset,
            )
        return terminal_artifact_list_out(
            window_id=window_id,
            artifacts=artifacts,
            total=total,
            limit=limit,
            offset=offset,
            artifact_scope=artifact_scope,
            project_path=project_path if artifact_scope == "project" else None,
        )

    async def create_window_artifact(
        self,
        client_id: UUID,
        window_id: UUID,
        payload: TerminalArtifactCreateIn,
        *,
        runtime: TerminalArtifactRuntimeDeps,
    ) -> TerminalArtifactOut:
        client = await self._require_window(client_id, window_id)
        scope = payload.artifact_scope
        project_path = payload.project_path.strip() if payload.project_path else None
        if scope == "project" and project_path is None:
            raise TerminalArtifactApiError(400, "project_path is required for project artifacts")
        draft = await self._draft_from_payload(
            payload,
            artifact_scope=scope,
            owner_user_id=client.owner_user_id,
        )
        artifact = await create_terminal_artifact(
            self._session,
            client_id=client_id,
            virtual_window_id=window_id,
            source_window_id=window_id,
            artifact_scope=scope,
            project_path=project_path if scope == "project" else None,
            artifact_kind=draft.artifact_kind,
            title=draft.title,
            metadata_json=metadata_with_artifact_model_selection(
                draft.metadata_json,
                payload.artifact_model_selection,
            ),
        )
        await self._session.commit()
        await self._session.refresh(artifact)
        self._schedule_generation(client_id, window_id, artifact, draft, runtime)
        return terminal_artifact_out(artifact, include_display_html=False)

    async def list_project_artifacts(
        self,
        client_id: UUID,
        project_path: str,
        *,
        limit: int,
        offset: int,
    ) -> ProjectArtifactListOut:
        await self._require_client(client_id)
        artifacts, total = await list_project_artifacts(
            self._session,
            client_id,
            project_path,
            limit=limit,
            offset=offset,
        )
        return project_artifact_list_out(
            project_path=project_path,
            artifacts=artifacts,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def read_project_artifact(
        self,
        client_id: UUID,
        project_path: str,
        artifact_id: UUID,
    ) -> TerminalArtifactOut:
        artifact = await self._require_project_artifact(client_id, project_path, artifact_id)
        return terminal_artifact_out(artifact)

    async def read_project_artifact_html(
        self,
        client_id: UUID,
        project_path: str,
        artifact_id: UUID,
    ) -> str:
        artifact = await self._require_project_artifact(client_id, project_path, artifact_id)
        if not artifact.display_html:
            raise TerminalArtifactApiError(404, "artifact html not ready")
        return artifact.display_html

    async def read_window_artifact(
        self,
        client_id: UUID,
        window_id: UUID,
        artifact_id: UUID,
    ) -> TerminalArtifactOut:
        artifact = await self._require_artifact(client_id, window_id, artifact_id)
        return terminal_artifact_out(artifact)

    async def read_window_artifact_html(
        self,
        client_id: UUID,
        window_id: UUID,
        artifact_id: UUID,
    ) -> str:
        artifact = await self._require_artifact(client_id, window_id, artifact_id)
        if not artifact.display_html:
            raise TerminalArtifactApiError(404, "artifact html not ready")
        return artifact.display_html

    async def local_client_id(self) -> UUID:
        client = await ensure_local_client(self._session)
        return client.id

    async def _require_client(self, client_id: UUID) -> Client:
        client = await get_client(self._session, client_id)
        if client is None:
            raise TerminalArtifactApiError(404, "client not found")
        return client

    async def _require_window(self, client_id: UUID, window_id: UUID) -> Client:
        client = await self._require_client(client_id)
        if await get_window_for_client(self._session, client_id, window_id) is None:
            raise TerminalArtifactApiError(404, "window not found")
        return client

    async def _require_artifact(
        self,
        client_id: UUID,
        window_id: UUID,
        artifact_id: UUID,
    ) -> TerminalArtifact:
        await self._require_client(client_id)
        artifact = await get_terminal_artifact_for_client(
            self._session,
            client_id,
            window_id,
            artifact_id,
            artifact_scope="terminal",
        )
        if artifact is None:
            raise TerminalArtifactApiError(404, "artifact not found")
        return artifact

    async def _require_project_artifact(
        self,
        client_id: UUID,
        project_path: str,
        artifact_id: UUID,
    ) -> TerminalArtifact:
        await self._require_client(client_id)
        artifact = await get_project_artifact_for_client(
            self._session,
            client_id,
            project_path,
            artifact_id,
        )
        if artifact is None:
            raise TerminalArtifactApiError(404, "artifact not found")
        return artifact

    async def _draft_from_payload(
        self,
        payload: TerminalArtifactCreateIn,
        *,
        artifact_scope: str,
        owner_user_id: str | None,
    ) -> TerminalArtifactDraft:
        await restore_artifact_plugin_files_to_disk(
            self._session,
            owner_user_id=owner_user_id,
        )
        try:
            plugin = get_artifact_plugin_registry_for_scope(
                artifact_scope,
                owner_user_id=owner_user_id,
            ).by_kind(payload.artifact_kind)
        except ValueError as exc:
            raise TerminalArtifactApiError(400, str(exc)) from exc
        return TerminalArtifactDraft.from_payload(
            payload,
            plugin=plugin,
            default_retention_seconds=get_settings().terminal_artifact_terminal_retention_seconds,
        )

    def _schedule_generation(
        self,
        client_id: UUID,
        window_id: UUID,
        artifact: TerminalArtifact,
        draft: TerminalArtifactDraft,
        runtime: TerminalArtifactRuntimeDeps,
    ) -> None:
        runtime.schedule_generation(
            TerminalArtifactGenerationRequest(
                client_id=client_id,
                window_id=window_id,
                artifact_id=artifact.id,
                prompt=draft.prompt,
                output_language=draft.output_language,
            ),
            session_factory=runtime.session_factory,
            tmux_manager=runtime.tmux_manager,
            terminal_broker=runtime.terminal_broker,
            registry=runtime.registry,
            ui_event_hub=runtime.ui_event_hub,
        )
