import { describe, expect, it } from "vitest";

import { projectTodoArtifactToTerminalArtifact } from "../src/components/projectTodoArtifacts";
import type { ProjectTodoArtifact } from "../src/types";

function linkedArtifact(overrides: Partial<ProjectTodoArtifact> = {}): ProjectTodoArtifact {
  return {
    id: "todo-artifact-link-1",
    artifact_id: "artifact-1",
    client_id: "client-1",
    window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: null,
    artifact_scope: "terminal",
    project_path: null,
    review_run_id: null,
    created_by_window_id: "window-1",
    title: "Requirement Review Report",
    artifact_kind: "requirement_review_report",
    status: "SUCCEEDED",
    purpose: "todo_artifact",
    agent_name: "codex",
    agent_status: null,
    metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
    last_error: null,
    started_at: "2026-06-08T00:00:00Z",
    completed_at: "2026-06-08T00:01:00Z",
    created_at: "2026-06-08T00:00:00Z",
    updated_at: "2026-06-08T00:01:00Z",
    ...overrides
  };
}

describe("projectTodoArtifactToTerminalArtifact", () => {
  it("uses the owning project path for terminal-scope linked artifacts", () => {
    const terminalArtifact = projectTodoArtifactToTerminalArtifact(
      linkedArtifact(),
      "/workspace/project"
    );

    expect(terminalArtifact.project_path).toBe("/workspace/project");
  });

  it("keeps an explicit artifact project path ahead of the surrounding context", () => {
    const terminalArtifact = projectTodoArtifactToTerminalArtifact(
      linkedArtifact({
        artifact_scope: "project",
        project_path: "/workspace/artifact-project"
      }),
      "/workspace/current-project"
    );

    expect(terminalArtifact.project_path).toBe("/workspace/artifact-project");
  });
});
