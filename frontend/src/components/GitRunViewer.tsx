import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";

import { fetchGitRuns } from "../api";
import { useI18n } from "../i18n";
import {
  basename,
  commitLabel,
  displayPath,
  fileCount,
  fileDelta,
  fileStatusTone,
  formatGitDateTime,
  gitDiffFileKey,
  gitRunTitle,
  shortSha,
  treeFileLabel
} from "../gitDiff";
import type { GitDiffCommit, GitDiffFile, GitWorktreeRun } from "../types";
import { GitDiffPatchView } from "./GitDiffPatchView";

type GitRunViewerProps = {
  clientId: string;
  windowId: string;
};

type SelectedDiff = {
  commit: GitDiffCommit;
  file: GitDiffFile;
};

type FileViewMode = "list" | "tree";

type GitFileTreeNode = {
  name: string;
  path: string;
  children: GitFileTreeNode[];
  files: GitDiffFile[];
};

type GitTreeDepthStyle = CSSProperties & {
  "--git-file-tree-depth": number;
};

function snapshotText(run: GitWorktreeRun, key: "start_snapshot_json" | "end_snapshot_json", field: string): string {
  const snapshot = run[key];
  const value = snapshot?.[field];
  return typeof value === "string" && value.trim() ? value : "-";
}

function filterCommits(commits: GitDiffCommit[], selectedSha: string): GitDiffCommit[] {
  if (selectedSha === "all") {
    return commits;
  }
  return commits.filter((commit) => commit.sha === selectedSha);
}

function firstDiffSelection(commits: GitDiffCommit[]): SelectedDiff | null {
  for (const commit of commits) {
    const file = commit.files?.[0];
    if (file) {
      return { commit, file };
    }
  }
  return null;
}

function selectionFromCommits(commits: GitDiffCommit[], selection: SelectedDiff | null): SelectedDiff | null {
  if (!selection) {
    return firstDiffSelection(commits);
  }
  const selectedFileKey = gitDiffFileKey(selection.file);
  for (const commit of commits) {
    if (commit.sha !== selection.commit.sha) {
      continue;
    }
    const file = commit.files?.find((candidate) => gitDiffFileKey(candidate) === selectedFileKey);
    if (file) {
      return { commit, file };
    }
  }
  return firstDiffSelection(commits);
}

function buildFileTree(files: GitDiffFile[]): GitFileTreeNode {
  const root: GitFileTreeNode = { name: "", path: "", children: [], files: [] };
  for (const file of files) {
    const parts = file.path.split("/").filter(Boolean);
    if (parts.length === 0) {
      root.files.push(file);
      continue;
    }
    let node = root;
    for (const part of parts.slice(0, -1)) {
      const path = node.path ? `${node.path}/${part}` : part;
      let child = node.children.find((candidate) => candidate.name === part);
      if (!child) {
        child = { name: part, path, children: [], files: [] };
        node.children.push(child);
      }
      node = child;
    }
    node.files.push(file);
  }
  sortFileTree(root);
  return root;
}

function sortFileTree(node: GitFileTreeNode): void {
  node.children.sort((left, right) => left.name.localeCompare(right.name));
  node.files.sort((left, right) => basename(left.path).localeCompare(basename(right.path)));
  node.children.forEach(sortFileTree);
}

function RunCard({ run }: { run: GitWorktreeRun }) {
  const { t } = useI18n();
  const [selectedCommitSha, setSelectedCommitSha] = useState("all");
  const [selectedDiff, setSelectedDiff] = useState<SelectedDiff | null>(null);
  const [fileViewMode, setFileViewMode] = useState<FileViewMode>("tree");
  const diff = run.session_diff_json;
  const commits = diff?.commits ?? [];
  const visibleCommits = useMemo(
    () => filterCommits(commits, selectedCommitSha),
    [commits, selectedCommitSha]
  );
  const activeDiff = useMemo(
    () => selectionFromCommits(visibleCommits, selectedDiff),
    [visibleCommits, selectedDiff]
  );
  const title = gitRunTitle(run);

  return (
    <article className="git-run-card">
      <header className="git-run-card-header">
        <strong>{title}</strong>
        <span className={`git-run-status ${run.pending_commit ? "pending" : ""}`}>
          {run.pending_commit ? t("git.run.pendingCommitStatus") : run.status}
        </span>
      </header>
      <dl className="detail-list git-run-meta">
        <dt>{t("git.run.type")}</dt>
        <dd>{run.run_type}</dd>
        <dt>{t("git.run.provider")}</dt>
        <dd>{run.agent_provider ?? "-"}</dd>
        <dt>{t("git.run.worktree")}</dt>
        <dd>{run.worktree_root ?? "-"}</dd>
        <dt>{t("git.run.discovery")}</dt>
        <dd>{run.discovery_method ?? "-"}</dd>
        <dt>{t("git.run.started")}</dt>
        <dd>{formatGitDateTime(run.started_at)}</dd>
        <dt>{t("git.run.ended")}</dt>
        <dd>{run.ended_at ? formatGitDateTime(run.ended_at) : "-"}</dd>
        <dt>{t("git.run.pendingCommit")}</dt>
        <dd>{run.pending_commit ? t("git.run.yes") : t("git.run.no")}</dd>
        {run.run_type === "tracking" && (
          <>
            <dt>{t("git.run.startHead")}</dt>
            <dd><code>{snapshotText(run, "start_snapshot_json", "head_sha")}</code></dd>
            <dt>{t("git.run.currentHead")}</dt>
            <dd><code>{snapshotText(run, "end_snapshot_json", "head_sha")}</code></dd>
          </>
        )}
      </dl>
      {diff?.head_moved && (
        <p className="git-run-head-range">
          HEAD <code>{shortSha(diff.start_head)}</code> {"->"} <code>{shortSha(diff.end_head)}</code>
        </p>
      )}
      {commits.length > 0 ? (
        <section className="git-commit-browser" aria-label={t("git.diff.changes")}>
          <label>
            <span>{t("git.run.commit")}</span>
            <select value={selectedCommitSha} onChange={(event) => setSelectedCommitSha(event.target.value)}>
              <option value="all">{t("git.run.allCommits", { count: commits.length })}</option>
              {commits.map((commit) => (
                <option key={commit.sha} value={commit.sha}>
                  {commitLabel(commit)}
                </option>
              ))}
            </select>
          </label>
          <div className="git-file-view-toggle" role="group" aria-label={t("git.run.fileDisplayMode")}>
            <button
              type="button"
              className={fileViewMode === "tree" ? "selected" : ""}
              onClick={() => setFileViewMode("tree")}
              aria-pressed={fileViewMode === "tree"}
            >
              {t("git.run.tree")}
            </button>
            <button
              type="button"
              className={fileViewMode === "list" ? "selected" : ""}
              onClick={() => setFileViewMode("list")}
              aria-pressed={fileViewMode === "list"}
            >
              {t("git.run.list")}
            </button>
          </div>
          <div className="git-commit-list">
            {visibleCommits.map((commit) => (
              <section key={commit.sha} className="git-commit-item">
                <header>
                  <div>
                    <strong>{commit.subject || t("git.run.untitledCommit")}</strong>
                    <code>{shortSha(commit.short_sha || commit.sha)}</code>
                  </div>
                  {commit.authored_at && <time>{formatGitDateTime(commit.authored_at)}</time>}
                </header>
                <CommitFileBrowser
                  commit={commit}
                  mode={fileViewMode}
                  selectedFileKey={activeDiff?.commit.sha === commit.sha ? gitDiffFileKey(activeDiff.file) : null}
                  onSelectFile={(file) => setSelectedDiff({ commit, file })}
                />
              </section>
            ))}
          </div>
          {activeDiff ? (
            <GitDiffPatchView
              commit={activeDiff.commit}
              file={activeDiff.file}
              className="git-run-inline-diff"
            />
          ) : (
            <p className="muted">{t("git.diff.selectFilePatch")}</p>
          )}
        </section>
      ) : (
        diff && <p className="muted">{t("git.run.noCommittedDiff")}</p>
      )}
    </article>
  );
}

function CommitFileBrowser({
  commit,
  mode,
  selectedFileKey,
  onSelectFile
}: {
  commit: GitDiffCommit;
  mode: FileViewMode;
  selectedFileKey: string | null;
  onSelectFile: (file: GitDiffFile) => void;
}) {
  const { t } = useI18n();
  const files = commit.files ?? [];
  const fileTree = useMemo(() => buildFileTree(files), [files]);

  if (files.length === 0) {
    return <p className="muted">{t("git.run.noFileChanges")}</p>;
  }
  if (mode === "tree") {
    return (
      <div className="git-file-tree" aria-label={t("git.run.changedFilesTree")}>
        {fileTree.files.map((file) => (
          <GitFileButton
            key={`${commit.sha}:${file.old_path ?? ""}:${file.path}`}
            file={file}
            label={treeFileLabel(file)}
            path={displayPath(file)}
            selected={gitDiffFileKey(file) === selectedFileKey}
            onSelect={() => onSelectFile(file)}
          />
        ))}
        {fileTree.children.map((node) => (
          <GitFileTreeBranch
            key={node.path}
            node={node}
            commitSha={commit.sha}
            depth={0}
            selectedFileKey={selectedFileKey}
            onSelectFile={onSelectFile}
          />
        ))}
      </div>
    );
  }
  return (
    <ul className="git-file-list">
      {files.map((file) => (
        <li key={`${commit.sha}:${file.old_path ?? ""}:${file.path}`}>
          <GitFileButton
            file={file}
            path={displayPath(file)}
            selected={gitDiffFileKey(file) === selectedFileKey}
            onSelect={() => onSelectFile(file)}
          />
        </li>
      ))}
    </ul>
  );
}

function GitFileTreeBranch({
  node,
  commitSha,
  depth,
  selectedFileKey,
  onSelectFile
}: {
  node: GitFileTreeNode;
  commitSha: string;
  depth: number;
  selectedFileKey: string | null;
  onSelectFile: (file: GitDiffFile) => void;
}) {
  return (
    <div className="git-file-tree-branch">
      <div className="git-file-tree-directory" style={{ "--git-file-tree-depth": depth } as GitTreeDepthStyle}>
        <span>{node.name}</span>
      </div>
      {node.files.map((file) => (
        <GitFileButton
          key={`${commitSha}:${file.old_path ?? ""}:${file.path}`}
          file={file}
          label={treeFileLabel(file)}
          path={displayPath(file)}
          depth={depth + 1}
          selected={gitDiffFileKey(file) === selectedFileKey}
          onSelect={() => onSelectFile(file)}
        />
      ))}
      {node.children.map((child) => (
        <GitFileTreeBranch
          key={child.path}
          node={child}
          commitSha={commitSha}
          depth={depth + 1}
          selectedFileKey={selectedFileKey}
          onSelectFile={onSelectFile}
        />
      ))}
    </div>
  );
}

function GitFileButton({
  file,
  label,
  path,
  depth = 0,
  selected = false,
  onSelect
}: {
  file: GitDiffFile;
  label?: string;
  path: string;
  depth?: number;
  selected?: boolean;
  onSelect: () => void;
}) {
  const statusTone = fileStatusTone(file.status);
  return (
    <button
      type="button"
      className={`git-file-button${selected ? " selected" : ""}`}
      style={{ "--git-file-tree-depth": depth } as GitTreeDepthStyle}
      onClick={onSelect}
      title={path}
      aria-pressed={selected}
    >
      <span className={`git-file-status ${statusTone}`}>{file.status ?? "modified"}</span>
      <span className="git-file-path">{label ?? path}</span>
      <span className="git-file-delta" aria-label={fileDelta(file)}>
        <span className="git-file-additions">+{fileCount(file.additions)}</span>
        <span className="git-file-deletions">-{fileCount(file.deletions)}</span>
      </span>
    </button>
  );
}

export function GitRunViewer({ clientId, windowId }: GitRunViewerProps) {
  const { t } = useI18n();
  const runsQuery = useQuery({
    queryKey: ["git-runs", clientId, windowId],
    queryFn: () => fetchGitRuns(clientId, windowId),
    refetchInterval: 10000
  });

  if (runsQuery.isLoading) {
    return <p className="muted">{t("git.run.loading")}</p>;
  }
  if (runsQuery.isError) {
    return <p className="error" role="alert">{t("git.run.loadFailed")}</p>;
  }
  if (!runsQuery.data?.supported) {
    return (
      <p className="muted">
        {t("git.run.noWorktree", { skill: "web-terminal-git-worktree" })}
      </p>
    );
  }
  if (runsQuery.data.runs.length === 0) {
    return <p className="muted">{t("git.run.empty")}</p>;
  }

  return (
    <div className="git-run-list">
      {runsQuery.data.runs.map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </div>
  );
}
