import type { GitDiffCommit, GitDiffFile, GitWorktreeRun } from "./types";

export type PatchLineTone = "addition" | "deletion" | "hunk" | "meta" | "context";

export type GitDiffCommitOption = {
  id: string;
  commit: GitDiffCommit;
  runId: string;
  runTitle: string;
  runStartedAt: string;
};

export function formatGitDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function shortSha(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "?";
}

export function fileCount(value: number | undefined): number {
  return Number.isFinite(value) ? Number(value) : 0;
}

export function fileDelta(file: GitDiffFile): string {
  return `+${fileCount(file.additions)} / -${fileCount(file.deletions)}`;
}

export function displayPath(file: GitDiffFile): string {
  if (file.old_path && file.old_path !== file.path) {
    return `${file.old_path} -> ${file.path}`;
  }
  return file.path;
}

export function basename(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : path;
}

export function treeFileLabel(file: GitDiffFile): string {
  if (file.old_path && file.old_path !== file.path) {
    return `${basename(file.old_path)} -> ${basename(file.path)}`;
  }
  return basename(file.path);
}

export function commitLabel(commit: GitDiffCommit): string {
  return `${shortSha(commit.short_sha || commit.sha)} ${commit.subject || "Untitled commit"}`;
}

export function fileStatusTone(status: string | undefined): string {
  const normalized = (status ?? "modified").toLowerCase();
  if (normalized === "added" || normalized === "add" || normalized === "a") {
    return "added";
  }
  if (normalized === "deleted" || normalized === "removed" || normalized === "delete" || normalized === "d") {
    return "deleted";
  }
  if (normalized === "renamed" || normalized === "rename" || normalized === "r") {
    return "renamed";
  }
  return "modified";
}

export function patchLineTone(line: string): PatchLineTone {
  if (line.startsWith("@@")) {
    return "hunk";
  }
  if (
    line.startsWith("diff --git") ||
    line.startsWith("index ") ||
    line.startsWith("new file mode ") ||
    line.startsWith("deleted file mode ") ||
    line.startsWith("similarity index ") ||
    line.startsWith("rename from ") ||
    line.startsWith("rename to ") ||
    line.startsWith("--- ") ||
    line.startsWith("+++ ")
  ) {
    return "meta";
  }
  if (line.startsWith("+")) {
    return "addition";
  }
  if (line.startsWith("-")) {
    return "deletion";
  }
  return "context";
}

export function patchLines(patch: string | undefined): string[] {
  const text = patch?.trimEnd();
  if (!text) {
    return ["No textual patch captured for this file."];
  }
  return text.split("\n");
}

export function gitDiffFileKey(file: GitDiffFile): string {
  return `${file.old_path ?? ""}\n${file.path}\n${file.status ?? ""}`;
}

export function gitRunTitle(run: GitWorktreeRun): string {
  return run.run_type === "tracking" ? "Worktree baseline" : `Agent run #${run.command_sequence}`;
}

export function collectGitDiffCommitOptions(runs: GitWorktreeRun[]): GitDiffCommitOption[] {
  const seen = new Set<string>();
  const options: GitDiffCommitOption[] = [];
  for (const run of runs) {
    for (const commit of run.session_diff_json?.commits ?? []) {
      if (!commit.sha || seen.has(commit.sha)) {
        continue;
      }
      seen.add(commit.sha);
      options.push({
        id: commit.sha,
        commit,
        runId: run.id,
        runTitle: gitRunTitle(run),
        runStartedAt: run.started_at
      });
    }
  }
  return options;
}
