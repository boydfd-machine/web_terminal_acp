import { describe, expect, it } from "vitest";

import {
  collectGitDiffCommitOptions,
  displayPath,
  gitDiffFileKey,
  patchLineTone
} from "../src/gitDiff";
import type { GitDiffCommit, GitDiffFile, GitWorktreeRun } from "../src/types";

function runWithCommits(id: string, commits: GitDiffCommit[]): GitWorktreeRun {
  return {
    id,
    virtual_window_id: "window-1",
    command_sequence: "1",
    agent_provider: "codex",
    status: "completed",
    run_type: "agent",
    worktree_root: "/repo/.worktrees/agent",
    main_repo_root: "/repo",
    discovery_method: "marker",
    start_snapshot_json: null,
    end_snapshot_json: null,
    session_diff_json: { commits },
    pending_commit: false,
    resolved_at: null,
    started_at: "2026-05-28T00:00:00Z",
    ended_at: "2026-05-28T00:01:00Z"
  };
}

describe("gitDiff helpers", () => {
  it("deduplicates commits across git runs while preserving run context", () => {
    const commit = { sha: "abcdef123456", subject: "Add diff browser", files: [] };
    const options = collectGitDiffCommitOptions([
      runWithCommits("run-1", [commit]),
      runWithCommits("run-2", [commit, { sha: "fedcba654321", subject: "Follow up", files: [] }])
    ]);

    expect(options.map((option) => option.id)).toEqual(["abcdef123456", "fedcba654321"]);
    expect(options[0].runId).toBe("run-1");
    expect(options[0].runTitle).toBe("Agent run #1");
  });

  it("keeps renamed files stable and readable", () => {
    const file: GitDiffFile = {
      old_path: "src/old.ts",
      path: "src/new.ts",
      status: "renamed"
    };

    expect(displayPath(file)).toBe("src/old.ts -> src/new.ts");
    expect(gitDiffFileKey(file)).toBe("src/old.ts\nsrc/new.ts\nrenamed");
  });

  it("classifies patch lines for diff rendering", () => {
    expect(patchLineTone("@@ -1 +1 @@")).toBe("hunk");
    expect(patchLineTone("diff --git a/a b/a")).toBe("meta");
    expect(patchLineTone("+added")).toBe("addition");
    expect(patchLineTone("-deleted")).toBe("deletion");
    expect(patchLineTone(" context")).toBe("context");
  });
});
