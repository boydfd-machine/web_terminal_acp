import type { ProjectArtifactVersion, ProjectArtifactList, TerminalArtifact } from "../types";

export type ProjectArtifactViewGroup = {
  artifact_kind: string;
  latest_artifact: TerminalArtifact;
  version_count: number;
  versions: ProjectArtifactVersion[];
};

export function projectArtifactGroups(data: ProjectArtifactList | null | undefined): ProjectArtifactViewGroup[] {
  if (data === null || data === undefined) {
    return [];
  }
  if (data.artifact_groups !== undefined) {
    return data.artifact_groups.map((group) => ({
      artifact_kind: group.artifact_kind,
      latest_artifact: group.latest_artifact,
      version_count: group.version_count,
      versions: [...group.versions]
    }));
  }
  return projectArtifactGroupsFromArtifacts(data.artifacts);
}

export function projectArtifactGroupsFromArtifacts(artifacts: TerminalArtifact[]): ProjectArtifactViewGroup[] {
  const groups = new Map<string, TerminalArtifact[]>();
  for (const artifact of artifacts) {
    const group = groups.get(artifact.artifact_kind);
    if (group === undefined) {
      groups.set(artifact.artifact_kind, [artifact]);
    } else {
      group.push(artifact);
    }
  }

  return Array.from(groups.entries()).map(([artifactKind, groupArtifacts]) => {
    const versions = [...groupArtifacts]
      .sort(compareArtifactsNewestFirst)
      .map((artifact, index, sortedArtifacts): ProjectArtifactVersion => ({
        artifact,
        version_number: sortedArtifacts.length - index,
        created_at: artifact.created_at,
        completed_at: artifact.completed_at,
        source_window_id: artifact.source_window_id,
        source_window_title: null,
        virtual_window_title: null
      }));
    return {
      artifact_kind: artifactKind,
      latest_artifact: versions[0].artifact,
      version_count: versions.length,
      versions
    };
  });
}

export function nextSelectedProjectArtifactId(
  groups: ProjectArtifactViewGroup[],
  selectedArtifactId: string | null,
  selectedArtifactKind: string | null
): string | null {
  if (groups.length === 0) {
    return null;
  }
  const selectedGroup = groups.find((group) => group.artifact_kind === selectedArtifactKind) ?? groups[0];
  const selectedVersionExists = selectedArtifactId !== null
    && selectedGroup.versions.some((version) => version.artifact.id === selectedArtifactId);
  if (selectedVersionExists) {
    return selectedArtifactId;
  }
  return selectedGroup.versions[0]?.artifact.id ?? null;
}

function compareArtifactsNewestFirst(left: TerminalArtifact, right: TerminalArtifact): number {
  const timeDifference = artifactSortTime(right) - artifactSortTime(left);
  if (timeDifference !== 0) {
    return timeDifference;
  }
  return right.id.localeCompare(left.id);
}

function artifactSortTime(artifact: TerminalArtifact): number {
  const value = artifact.completed_at ?? artifact.created_at;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}
