import type { TerminalArtifact } from "./types";

const ACTIVE_ARTIFACT_STATUSES = new Set(["PENDING", "RUNNING"]);

export function isActiveTerminalArtifact(artifact: TerminalArtifact): boolean {
  return artifact.ephemeral_window_id !== null || ACTIVE_ARTIFACT_STATUSES.has(artifact.status.toUpperCase());
}

export function hasActiveTerminalArtifact(artifacts: TerminalArtifact[]): boolean {
  return artifacts.some(isActiveTerminalArtifact);
}

export function selectArtifactTerminalCarrier(
  artifacts: TerminalArtifact[],
  selectedArtifactId: string | null
): TerminalArtifact | null {
  if (selectedArtifactId === null) {
    return null;
  }

  const artifact = artifacts.find((candidate) => candidate.id === selectedArtifactId) ?? null;
  return artifact !== null
    && isActiveTerminalArtifact(artifact)
    ? artifact
    : null;
}

export function artifactTerminalCarrierStatusLabel(artifact: TerminalArtifact): string {
  switch (artifact.status.toUpperCase()) {
    case "PENDING":
      return "Preparing...";
    case "RUNNING":
      return "Running...";
    case "SUCCEEDED":
      return "Completed";
    case "FAILED":
      return "Failed";
    default:
      return artifact.status.toLowerCase();
  }
}
