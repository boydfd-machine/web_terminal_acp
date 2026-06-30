from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_artifacts.infrastructure.repository import create_terminal_artifact
from app.models import TerminalArtifact


async def create_terminal_artifact_record(
    session: AsyncSession,
    *,
    client_id: UUID,
    virtual_window_id: UUID,
    source_window_id: UUID | None,
    artifact_scope: str,
    project_path: str | None,
    artifact_kind: str,
    title: str,
    metadata_json: dict | None,
) -> TerminalArtifact:
    return await create_terminal_artifact(
        session,
        client_id=client_id,
        virtual_window_id=virtual_window_id,
        source_window_id=source_window_id,
        artifact_scope=artifact_scope,
        project_path=project_path,
        artifact_kind=artifact_kind,
        title=title,
        metadata_json=metadata_json,
    )
