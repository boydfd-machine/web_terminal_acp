from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.contexts.terminal_artifacts.api.schemas import (
    ProjectArtifactGroupOut,
    ProjectArtifactListOut,
    ProjectArtifactVersionOut,
    TerminalArtifactListOut,
    TerminalArtifactOut,
)
from app.models import TerminalArtifact


def terminal_artifact_out(
    artifact: TerminalArtifact,
    *,
    include_display_html: bool = True,
) -> TerminalArtifactOut:
    return TerminalArtifactOut(
        id=artifact.id,
        client_id=artifact.client_id,
        virtual_window_id=artifact.virtual_window_id,
        source_window_id=artifact.source_window_id,
        ephemeral_window_id=artifact.ephemeral_window_id,
        artifact_scope=artifact.artifact_scope,
        project_path=artifact.project_path,
        artifact_kind=artifact.artifact_kind,
        title=artifact.title,
        status=artifact.status.value,
        content_json=artifact.content_json,
        display_html=artifact.display_html if include_display_html else None,
        metadata_json=artifact.metadata_json,
        last_error=artifact.last_error,
        started_at=artifact.started_at,
        completed_at=artifact.completed_at,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def terminal_artifact_list_out(
    *,
    window_id: UUID,
    artifacts: Sequence[TerminalArtifact],
    total: int,
    limit: int,
    offset: int,
    artifact_scope: str = "terminal",
    project_path: str | None = None,
) -> TerminalArtifactListOut:
    return TerminalArtifactListOut(
        window_id=window_id,
        artifact_scope=artifact_scope,
        project_path=project_path,
        artifacts=[
            terminal_artifact_out(artifact, include_display_html=False)
            for artifact in artifacts
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


def project_artifact_list_out(
    *,
    project_path: str,
    artifacts: Sequence[TerminalArtifact],
    total: int,
    limit: int,
    offset: int,
) -> ProjectArtifactListOut:
    artifact_items = [
        terminal_artifact_out(artifact, include_display_html=False)
        for artifact in artifacts
    ]
    return ProjectArtifactListOut(
        project_path=project_path,
        artifacts=artifact_items,
        artifact_groups=project_artifact_groups_out(artifacts),
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


def project_artifact_groups_out(
    artifacts: Sequence[TerminalArtifact],
) -> list[ProjectArtifactGroupOut]:
    grouped: dict[str, list[TerminalArtifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.artifact_kind, []).append(artifact)

    groups: list[ProjectArtifactGroupOut] = []
    for artifact_kind, group_artifacts in grouped.items():
        if not group_artifacts:
            continue
        versions = [
            ProjectArtifactVersionOut(
                artifact=terminal_artifact_out(artifact, include_display_html=False),
                version_number=len(group_artifacts) - index,
                created_at=artifact.created_at,
                completed_at=artifact.completed_at,
                source_window_id=artifact.source_window_id,
                source_window_title=artifact.source_window.title if artifact.source_window is not None else None,
                virtual_window_title=artifact.virtual_window.title if artifact.virtual_window is not None else None,
            )
            for index, artifact in enumerate(group_artifacts)
        ]
        groups.append(
            ProjectArtifactGroupOut(
                artifact_kind=artifact_kind,
                latest_artifact=versions[0].artifact,
                version_count=len(versions),
                versions=versions,
            )
        )
    return groups
