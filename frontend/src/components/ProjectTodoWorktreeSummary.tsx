import { useMemo, useState } from "react";

import { collectGitDiffCommitOptions } from "../gitDiff";
import { useI18n } from "../i18n";
import type { ProjectTodoWorktree } from "../types";
import { GitDiffBrowserModal } from "./GitDiffBrowserModal";
import { GitMergeStatusBadge, gitMergeStatusDetail } from "./GitMergeStatus";
import { UiIcon } from "./UiIcon";

export function ProjectTodoWorktreeSummary({
  clientId,
  isMobileLayout = false,
  worktree
}: {
  clientId: string;
  isMobileLayout?: boolean;
  worktree: ProjectTodoWorktree | null;
}) {
  const { t } = useI18n();
  const [diffOpen, setDiffOpen] = useState(false);
  const diffRuns = worktree?.diff_runs ?? [];
  const diffWindowId = worktree?.window_id ?? diffRuns[0]?.virtual_window_id ?? null;
  const diffAvailable = useMemo(
    () => collectGitDiffCommitOptions(diffRuns).length > 0,
    [diffRuns]
  );

  if (worktree === null) {
    return <p className="muted">{t("projectTodo.worktree.empty")}</p>;
  }
  const commits = worktree.commits ?? [];
  return (
    <div className="project-todo-worktree">
      <dl>
        <dt>{t("projectTodo.worktree.branch")}</dt>
        <dd>{worktree.branch ?? "-"}</dd>
        <dt>{t("projectTodo.worktree.worktree")}</dt>
        <dd>{worktree.worktree_root ?? "-"}</dd>
        <dt>{t("projectTodo.worktree.merge")}</dt>
        <dd>
          <span className={worktree.merge_attention_required ? "project-todo-merge-status attention" : "project-todo-merge-status"}>
            <GitMergeStatusBadge source={worktree} />
            <span>{gitMergeStatusDetail(worktree, t)}</span>
          </span>
        </dd>
        <dt>{t("projectTodo.worktree.head")}</dt>
        <dd>{worktree.end_head ?? "-"}</dd>
      </dl>
      {diffAvailable && diffWindowId && (
        <button
          type="button"
          className="project-todo-worktree-diff-button"
          aria-label={t("git.diff.title")}
          title={t("git.diff.title")}
          onClick={() => setDiffOpen(true)}
        >
          <UiIcon name="branch-plus" />
          <span>{t("git.diff.title")}</span>
        </button>
      )}
      {commits.length > 0 ? (
        <ul>
          {commits.slice(0, 6).map((commit, index) => (
            <li key={commit.sha ?? `${commit.subject ?? "commit"}-${index}`}>
              <strong>{commit.short_sha ?? shortSha(commit.sha)}</strong>
              <span>{commit.subject ?? t("git.run.untitledCommit")}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{t("projectTodo.worktree.noCommits")}</p>
      )}
      {diffOpen && diffWindowId && (
        <GitDiffBrowserModal
          clientId={clientId}
          windowId={diffWindowId}
          isMobileLayout={isMobileLayout}
          fallbackRuns={diffRuns}
          onClose={() => setDiffOpen(false)}
        />
      )}
    </div>
  );
}

function shortSha(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "?";
}
