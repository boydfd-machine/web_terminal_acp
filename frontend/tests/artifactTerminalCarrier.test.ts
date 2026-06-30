import { describe, expect, it } from "vitest";

import {
  artifactTerminalCarrierStatusLabel,
  hasActiveTerminalArtifact,
  isActiveTerminalArtifact,
  selectArtifactTerminalCarrier
} from "../src/artifactTerminalCarrier";
import type { TerminalArtifact } from "../src/types";

function artifact(overrides: Partial<TerminalArtifact>): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: "ephemeral-1",
    artifact_scope: "terminal",
    project_path: null,
    artifact_kind: "agent_trace_graph",
    title: "Trace graph",
    status: "RUNNING",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: null,
    created_at: "2026-06-02T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    ...overrides
  };
}

describe("artifact terminal carrier", () => {
  it("selects only the requested active artifact as the terminal carrier", () => {
    const completed = artifact({ id: "done", status: "SUCCEEDED" });
    const running = artifact({ id: "running", status: "RUNNING" });

    expect(selectArtifactTerminalCarrier([completed, running], null)).toBeNull();
    expect(selectArtifactTerminalCarrier([completed, running], "running")).toBe(running);
    expect(isActiveTerminalArtifact(running)).toBe(true);
    expect(hasActiveTerminalArtifact([completed, running])).toBe(true);
  });

  it("selects completed artifacts while their terminal is retained", () => {
    const running = artifact({ id: "running", status: "RUNNING" });
    const completed = artifact({ id: "done", status: "SUCCEEDED" });

    expect(selectArtifactTerminalCarrier([running, completed], "done")).toBe(completed);
  });

  it("does not select completed artifacts after their terminal is cleaned up", () => {
    const running = artifact({ id: "running", status: "RUNNING" });
    const completed = artifact({ id: "done", status: "SUCCEEDED", ephemeral_window_id: null });

    expect(selectArtifactTerminalCarrier([running, completed], "done")).toBeNull();
  });

  it("labels active artifact generation states", () => {
    expect(artifactTerminalCarrierStatusLabel(artifact({ status: "PENDING" }))).toBe("Preparing...");
    expect(artifactTerminalCarrierStatusLabel(artifact({ status: "RUNNING" }))).toBe("Running...");
    expect(artifactTerminalCarrierStatusLabel(artifact({ status: "SUCCEEDED" }))).toBe("Completed");
    expect(artifactTerminalCarrierStatusLabel(artifact({ status: "FAILED" }))).toBe("Failed");
    expect(artifactTerminalCarrierStatusLabel(artifact({ status: "CUSTOM" }))).toBe("custom");
  });
});
