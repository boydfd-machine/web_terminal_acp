from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import TerminalArtifact, TerminalArtifactStatus


async def create_terminal_artifact(
    session: AsyncSession,
    *,
    client_id: UUID,
    virtual_window_id: UUID,
    artifact_kind: str,
    title: str,
    source_window_id: UUID | None = None,
    artifact_scope: str = "terminal",
    project_path: str | None = None,
    metadata_json: dict | None = None,
) -> TerminalArtifact:
    artifact = TerminalArtifact(
        client_id=client_id,
        virtual_window_id=virtual_window_id,
        source_window_id=source_window_id,
        artifact_scope=artifact_scope,
        project_path=project_path,
        artifact_kind=artifact_kind,
        title=title,
        status=TerminalArtifactStatus.pending,
        metadata_json=metadata_json,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def get_terminal_artifact_for_client(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    artifact_id: UUID,
    *,
    artifact_scope: str | None = None,
) -> TerminalArtifact | None:
    filters = [
        TerminalArtifact.id == artifact_id,
        TerminalArtifact.client_id == client_id,
        TerminalArtifact.virtual_window_id == window_id,
    ]
    if artifact_scope is not None:
        filters.append(TerminalArtifact.artifact_scope == artifact_scope)
    return await session.scalar(
        select(TerminalArtifact).where(*filters)
    )


async def get_project_artifact_for_client(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    artifact_id: UUID,
) -> TerminalArtifact | None:
    return await session.scalar(
        select(TerminalArtifact).where(
            TerminalArtifact.id == artifact_id,
            TerminalArtifact.client_id == client_id,
            TerminalArtifact.artifact_scope == "project",
            TerminalArtifact.project_path == project_path,
        )
    )


async def list_terminal_artifacts_for_window(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    *,
    limit: int,
    offset: int,
    artifact_scope: str = "terminal",
) -> tuple[list[TerminalArtifact], int]:
    filters = (
        TerminalArtifact.client_id == client_id,
        TerminalArtifact.virtual_window_id == window_id,
        TerminalArtifact.artifact_scope == artifact_scope,
    )
    total = await session.scalar(
        select(sa_func.count()).select_from(TerminalArtifact).where(*filters)
    )
    items = list(
        await session.scalars(
            select(TerminalArtifact)
            .where(*filters)
            .order_by(desc(TerminalArtifact.created_at), desc(TerminalArtifact.id))
            .offset(offset)
            .limit(limit)
        )
    )
    return items, int(total or 0)


async def list_project_artifacts(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[TerminalArtifact], int]:
    filters = (
        TerminalArtifact.client_id == client_id,
        TerminalArtifact.artifact_scope == "project",
        TerminalArtifact.project_path == project_path,
    )
    total = await session.scalar(
        select(sa_func.count()).select_from(TerminalArtifact).where(*filters)
    )
    items = list(
        await session.scalars(
            select(TerminalArtifact)
            .options(
                selectinload(TerminalArtifact.source_window),
                selectinload(TerminalArtifact.virtual_window),
            )
            .where(*filters)
            .order_by(desc(TerminalArtifact.created_at), desc(TerminalArtifact.id))
            .offset(offset)
            .limit(limit)
        )
    )
    return items, int(total or 0)


async def latest_succeeded_project_artifact(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    artifact_kind: str,
    *,
    exclude_artifact_id: UUID | None = None,
) -> TerminalArtifact | None:
    filters = [
        TerminalArtifact.client_id == client_id,
        TerminalArtifact.artifact_scope == "project",
        TerminalArtifact.project_path == project_path,
        TerminalArtifact.artifact_kind == artifact_kind,
        TerminalArtifact.status == TerminalArtifactStatus.succeeded,
    ]
    if exclude_artifact_id is not None:
        filters.append(TerminalArtifact.id != exclude_artifact_id)
    return await session.scalar(
        select(TerminalArtifact)
        .where(*filters)
        .order_by(desc(TerminalArtifact.completed_at), desc(TerminalArtifact.created_at), desc(TerminalArtifact.id))
        .limit(1)
    )


async def list_incomplete_terminal_artifacts(session: AsyncSession) -> list[TerminalArtifact]:
    return list(
        await session.scalars(
            select(TerminalArtifact)
            .where(
                TerminalArtifact.status.in_(
                    [TerminalArtifactStatus.pending, TerminalArtifactStatus.running]
                )
            )
            .order_by(TerminalArtifact.created_at, TerminalArtifact.id)
        )
    )


async def mark_artifact_running(
    session: AsyncSession,
    artifact: TerminalArtifact,
    *,
    ephemeral_window_id: UUID | None = None,
) -> TerminalArtifact:
    now = datetime.now(UTC)
    artifact.status = TerminalArtifactStatus.running
    artifact.started_at = artifact.started_at or now
    artifact.ephemeral_window_id = ephemeral_window_id
    artifact.last_error = None
    await session.flush()
    return artifact


async def mark_artifact_succeeded(
    session: AsyncSession,
    artifact: TerminalArtifact,
    *,
    content_json: dict,
    display_html: str | None,
    metadata_json: dict | None = None,
) -> TerminalArtifact:
    artifact.status = TerminalArtifactStatus.succeeded
    artifact.content_json = content_json
    artifact.display_html = display_html
    if metadata_json is not None:
        artifact.metadata_json = metadata_json
    artifact.last_error = None
    artifact.completed_at = datetime.now(UTC)
    await session.flush()
    return artifact


async def mark_artifact_failed(
    session: AsyncSession,
    artifact: TerminalArtifact,
    *,
    error: str,
    metadata_json: dict | None = None,
) -> TerminalArtifact:
    artifact.status = TerminalArtifactStatus.failed
    artifact.last_error = error
    if metadata_json is not None:
        artifact.metadata_json = metadata_json
    artifact.completed_at = datetime.now(UTC)
    await session.flush()
    return artifact
