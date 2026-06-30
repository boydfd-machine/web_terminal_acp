import { describe, expect, it } from "vitest";

import {
  nextSelectedProjectArtifactId,
  projectArtifactGroups,
  projectArtifactGroupsFromArtifacts
} from "../src/components/projectArtifactsModel";
import type { ProjectArtifactList, TerminalArtifact } from "../src/types";

function artifact(overrides: Partial<TerminalArtifact>): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: null,
    artifact_scope: "project",
    project_path: "/workspace",
    artifact_kind: "user_journey",
    title: "User journey",
    status: "SUCCEEDED",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: "2026-06-07T08:00:00Z",
    created_at: "2026-06-07T08:00:00Z",
    updated_at: "2026-06-07T08:00:00Z",
    ...overrides
  };
}

describe("project artifact grouping model", () => {
  it("groups flat project artifacts into newest-first versions", () => {
    const oldJourney = artifact({
      id: "journey-1",
      title: "Journey v1",
      completed_at: "2026-06-07T08:00:00Z",
      created_at: "2026-06-07T08:00:00Z"
    });
    const prototype = artifact({
      id: "prototype-1",
      artifact_kind: "low_fi_prototype",
      title: "Prototype v1",
      completed_at: "2026-06-07T08:30:00Z",
      created_at: "2026-06-07T08:30:00Z"
    });
    const newJourney = artifact({
      id: "journey-2",
      title: "Journey v2",
      completed_at: "2026-06-07T09:00:00Z",
      created_at: "2026-06-07T09:00:00Z"
    });

    const groups = projectArtifactGroupsFromArtifacts([newJourney, prototype, oldJourney]);

    expect(groups.map((group) => group.artifact_kind)).toEqual(["user_journey", "low_fi_prototype"]);
    expect(groups[0].latest_artifact.id).toBe("journey-2");
    expect(groups[0].version_count).toBe(2);
    expect(groups[0].versions.map((version) => [version.version_number, version.artifact.id])).toEqual([
      [2, "journey-2"],
      [1, "journey-1"]
    ]);
  });

  it("prefers server-provided project artifact groups", () => {
    const latest = artifact({ id: "journey-2", title: "Journey v2" });
    const list: ProjectArtifactList = {
      project_path: "/workspace",
      artifacts: [latest],
      artifact_groups: [
        {
          artifact_kind: "user_journey",
          latest_artifact: latest,
          version_count: 2,
          versions: [
            {
              artifact: latest,
              version_number: 2,
              created_at: latest.created_at,
              completed_at: latest.completed_at,
              source_window_id: "window-1",
              source_window_title: "Summary terminal",
              virtual_window_title: "Summary terminal"
            }
          ]
        }
      ],
      total: 1,
      limit: 50,
      offset: 0,
      has_more: false
    };

    expect(projectArtifactGroups(list)[0].versions[0].source_window_title).toBe("Summary terminal");
  });

  it("keeps selected versions inside the selected artifact type", () => {
    const groups = projectArtifactGroupsFromArtifacts([
      artifact({ id: "journey-2", completed_at: "2026-06-07T09:00:00Z" }),
      artifact({ id: "journey-1", completed_at: "2026-06-07T08:00:00Z" }),
      artifact({
        id: "prototype-1",
        artifact_kind: "low_fi_prototype",
        completed_at: "2026-06-07T08:30:00Z"
      })
    ]);

    expect(nextSelectedProjectArtifactId(groups, null, null)).toBe("journey-2");
    expect(nextSelectedProjectArtifactId(groups, "journey-1", "user_journey")).toBe("journey-1");
    expect(nextSelectedProjectArtifactId(groups, "journey-1", "low_fi_prototype")).toBe("prototype-1");
  });
});
