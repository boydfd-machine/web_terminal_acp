from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_artifacts.infrastructure.repository import latest_succeeded_project_artifact
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.models import TerminalArtifact


@dataclass(frozen=True)
class ProjectArtifactWorkspace:
    original_path: str
    draft_tmp_path: str
    output_path: str
    content_json: dict[str, Any]

    @property
    def prompt_instructions(self) -> str:
        return (
            "\nProject artifact incremental update contract:\n"
            f"- Original artifact file A is {self.original_path}. Treat A as read-only reference.\n"
            f"- Editable draft file B.tmp is {self.draft_tmp_path}. Modify only B.tmp.\n"
            "- If B.tmp is a starter layer generated from todo context rather than a previous reviewed "
            "artifact, complete it using the todo context instead of preserving placeholder text.\n"
            f"- Final output file B is {self.output_path}. When B.tmp is complete and valid JSON, "
            f"rename B.tmp to B with `mv {self.draft_tmp_path} {self.output_path}`.\n"
            "- Do not write the artifact JSON into chat. The system only watches for B.\n"
        )


def project_artifact_output_path(artifact_id: UUID) -> str:
    return f"{_artifact_path_prefix(artifact_id)}-updated.json"


async def project_artifact_workspace_for(
    session: AsyncSession,
    artifact: TerminalArtifact,
    plugin: object,
) -> ProjectArtifactWorkspace | None:
    if artifact.artifact_scope != "project":
        return None
    if not artifact.project_path:
        raise ValueError("project artifact is missing project_path")
    previous = await latest_succeeded_project_artifact(
        session,
        artifact.client_id,
        artifact.project_path,
        artifact.artifact_kind,
        exclude_artifact_id=artifact.id,
    )
    return build_project_artifact_workspace(
        artifact.id,
        previous.content_json if previous is not None else None,
        plugin,
        initial_context=artifact.metadata_json if isinstance(artifact.metadata_json, dict) else None,
    )


def build_project_artifact_workspace(
    artifact_id: UUID,
    previous_content_json: dict[str, Any] | None,
    plugin: object,
    *,
    initial_context: dict[str, Any] | None = None,
) -> ProjectArtifactWorkspace:
    content = _initial_content(previous_content_json, plugin, initial_context)
    prefix = _artifact_path_prefix(artifact_id)
    return ProjectArtifactWorkspace(
        original_path=f"{prefix}-original.json",
        draft_tmp_path=f"{prefix}-updated.json.tmp",
        output_path=f"{prefix}-updated.json",
        content_json=content,
    )


async def write_project_artifact_workspace(
    broker: TerminalBroker,
    client_id: UUID,
    workspace: ProjectArtifactWorkspace,
) -> None:
    data = json.dumps(workspace.content_json, ensure_ascii=False, indent=2).encode("utf-8")
    await broker.write_file_bytes(client_id, workspace.original_path, data, overwrite=True)
    await broker.write_file_bytes(client_id, workspace.draft_tmp_path, data, overwrite=True)


def _initial_content(
    previous_content_json: dict[str, Any] | None,
    plugin: object,
    initial_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(previous_content_json, dict):
        return previous_content_json
    initial_content = getattr(plugin, "initial_content", None)
    if callable(initial_content):
        try:
            value = initial_content(initial_context or {})
        except TypeError:
            value = initial_content()
        if isinstance(value, dict):
            return value
    return {"artifact_kind": getattr(plugin, "artifact_kind", "project_artifact")}


def _artifact_path_prefix(artifact_id: UUID) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(artifact_id))
    return f"{tempfile.gettempdir()}/web-terminal-project-artifact-{safe_id}"
