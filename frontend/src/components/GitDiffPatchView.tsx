import { useI18n } from "../i18n";
import {
  commitLabel,
  displayPath,
  fileCount,
  fileStatusTone,
  patchLines,
  patchLineTone
} from "../gitDiff";
import type { GitDiffCommit, GitDiffFile } from "../types";

type GitDiffPatchViewProps = {
  commit: GitDiffCommit;
  file: GitDiffFile;
  className?: string;
};

export function GitDiffPatchView({ commit, file, className }: GitDiffPatchViewProps) {
  const { t } = useI18n();
  const tone = fileStatusTone(file.status);
  const classes = ["git-diff-browser-diff", tone, className].filter(Boolean).join(" ");
  return (
    <section className={classes} aria-label={t("git.diff.fileDiff")}>
      <header className="git-diff-browser-diff-header">
        <div>
          <strong>{displayPath(file)}</strong>
          <p>{commitLabel(commit)}</p>
        </div>
        <div className="git-diff-modal-meta">
          <span className={`git-file-status ${tone}`}>{file.status ?? "modified"}</span>
          <span className="git-file-additions">+{fileCount(file.additions)}</span>
          <span className="git-file-deletions">-{fileCount(file.deletions)}</span>
        </div>
      </header>
      <div className="git-diff-patch" role="region" aria-label={t("git.diff.patch")}>
        {patchLines(file.patch).map((line, index) => (
          <div key={`${index}:${line}`} className={`git-diff-line ${patchLineTone(line)}`}>
            <span className="git-diff-line-number">{index + 1}</span>
            <code>{line || " "}</code>
          </div>
        ))}
      </div>
    </section>
  );
}
