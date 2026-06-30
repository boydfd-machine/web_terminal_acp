import type { TranslateFn } from "../i18n";
import type { ProjectTodoArtifact, TerminalArtifact } from "../types";
import { artifactKindLabel } from "./windowDetailData";

export function projectTodoArtifactAgentLabel(artifact: ProjectTodoArtifact): string {
  return artifact.agent_name?.trim() || artifactKindLabel(artifact.artifact_kind);
}

export function projectTodoArtifactStatusText(status: string, t?: TranslateFn): string {
  switch (status.toUpperCase()) {
    case "PENDING":
      return t?.("artifacts.status.pending") ?? "pending";
    case "RUNNING":
      return t?.("artifacts.status.running") ?? "running";
    case "SUCCEEDED":
      return t?.("artifacts.status.ready") ?? "ready";
    case "FAILED":
      return t?.("artifacts.status.failed") ?? "failed";
    default:
      return status.toLowerCase();
  }
}

export function projectTodoArtifactHasTerminal(artifact: ProjectTodoArtifact): boolean {
  return artifact.ephemeral_window_id !== null || ["PENDING", "RUNNING"].includes(artifact.status.toUpperCase());
}

export function projectTodoArtifactToTerminalArtifact(
  artifact: ProjectTodoArtifact,
  projectPath?: string | null
): TerminalArtifact {
  return {
    id: artifact.artifact_id,
    client_id: artifact.client_id,
    virtual_window_id: artifact.window_id,
    source_window_id: artifact.source_window_id,
    ephemeral_window_id: artifact.ephemeral_window_id,
    artifact_scope: artifact.artifact_scope,
    project_path: artifact.project_path ?? projectPath ?? null,
    artifact_kind: artifact.artifact_kind,
    title: artifact.title,
    status: artifact.status,
    content_json: null,
    display_html: null,
    metadata_json: artifact.metadata_json,
    last_error: artifact.last_error,
    started_at: artifact.started_at,
    completed_at: artifact.completed_at,
    created_at: artifact.created_at,
    updated_at: artifact.updated_at,
  };
}
