import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchGitRuns } from "../api";
import { useI18n, type TranslateFn } from "../i18n";
import {
  collectGitDiffCommitOptions,
  commitLabel,
  displayPath,
  fileCount,
  fileDelta,
  fileStatusTone,
  formatGitDateTime,
  gitDiffFileKey,
  shortSha
} from "../gitDiff";
import type { GitDiffCommitOption } from "../gitDiff";
import type { GitDiffFile, GitWorktreeRun } from "../types";
import { GitDiffPatchView } from "./GitDiffPatchView";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type GitDiffBrowserStep = "commits" | "files" | "diff";

type GitDiffBrowserModalProps = {
  clientId: string;
  windowId: string;
  isMobileLayout: boolean;
  fallbackRuns?: GitWorktreeRun[];
  shortcutLabel?: string;
  onClose: () => void;
};

function selectDefaultCommit(options: GitDiffCommitOption[]): GitDiffCommitOption | null {
  return options.find((option) => (option.commit.files ?? []).length > 0) ?? options[0] ?? null;
}

function selectDefaultFile(option: GitDiffCommitOption | null): GitDiffFile | null {
  return option?.commit.files?.[0] ?? null;
}

function commitFileCount(option: GitDiffCommitOption): number {
  return option.commit.files?.length ?? 0;
}

function commitSummary(option: GitDiffCommitOption, t: TranslateFn): string {
  const commit = option.commit;
  const files = commitFileCount(option);
  const authored = commit.authored_at ? formatGitDateTime(commit.authored_at) : null;
  const pieces = [
    shortSha(commit.short_sha || commit.sha),
    t("git.diff.fileCount", { count: files }),
    authored,
    option.runTitle
  ].filter(Boolean);
  return pieces.join(" | ");
}

function ensureSelectedCommit(
  options: GitDiffCommitOption[],
  selectedCommitId: string | null
): GitDiffCommitOption | null {
  const selected = options.find((option) => option.id === selectedCommitId) ?? null;
  return selected ?? selectDefaultCommit(options);
}

function ensureSelectedFile(
  selectedCommit: GitDiffCommitOption | null,
  selectedFileKey: string | null
): GitDiffFile | null {
  const files = selectedCommit?.commit.files ?? [];
  return files.find((file) => gitDiffFileKey(file) === selectedFileKey) ?? files[0] ?? null;
}

function CommitList({
  options,
  selectedCommitId,
  onSelectCommit
}: {
  options: GitDiffCommitOption[];
  selectedCommitId: string | null;
  onSelectCommit: (option: GitDiffCommitOption) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="git-diff-browser-list" role="list" aria-label={t("git.diff.commits")}>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          className={`git-diff-browser-row${selectedCommitId === option.id ? " selected" : ""}`}
          onClick={() => onSelectCommit(option)}
        >
          <span className="git-diff-browser-row-title">{option.commit.subject || t("git.diff.untitledCommit")}</span>
          <span className="git-diff-browser-row-meta">{commitSummary(option, t)}</span>
        </button>
      ))}
    </div>
  );
}

function FileList({
  commitOption,
  selectedFileKey,
  onSelectFile
}: {
  commitOption: GitDiffCommitOption | null;
  selectedFileKey: string | null;
  onSelectFile: (file: GitDiffFile) => void;
}) {
  const { t } = useI18n();
  const files = commitOption?.commit.files ?? [];

  if (!commitOption) {
    return <p className="muted git-diff-browser-empty">{t("git.diff.selectCommitFirst")}</p>;
  }
  if (files.length === 0) {
    return <p className="muted git-diff-browser-empty">{t("git.run.noFileChanges")}</p>;
  }

  return (
    <div className="git-diff-browser-list" role="list" aria-label={t("git.diff.changedFiles")}>
      {files.map((file) => {
        const key = gitDiffFileKey(file);
        const tone = fileStatusTone(file.status);
        return (
          <button
            key={key}
            type="button"
            className={`git-diff-browser-row git-diff-browser-file-row${selectedFileKey === key ? " selected" : ""}`}
            onClick={() => onSelectFile(file)}
            title={displayPath(file)}
          >
            <span className={`git-file-status ${tone}`}>{file.status ?? "modified"}</span>
            <span className="git-diff-browser-row-title">{displayPath(file)}</span>
            <span className="git-file-delta" aria-label={fileDelta(file)}>
              <span className="git-file-additions">+{fileCount(file.additions)}</span>
              <span className="git-file-deletions">-{fileCount(file.deletions)}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function GitDiffBrowserModal({
  clientId,
  windowId,
  isMobileLayout,
  fallbackRuns = [],
  shortcutLabel = "Git diff",
  onClose
}: GitDiffBrowserModalProps) {
  const { t } = useI18n();
  const [selectedCommitId, setSelectedCommitId] = useState<string | null>(null);
  const [selectedFileKey, setSelectedFileKey] = useState<string | null>(null);
  const [mobileStep, setMobileStep] = useState<GitDiffBrowserStep>("commits");
  const panelRef = useRef<HTMLElement | null>(null);
  const runsQuery = useQuery({
    queryKey: ["git-runs", clientId, windowId],
    queryFn: () => fetchGitRuns(clientId, windowId),
    enabled: fallbackRuns.length === 0,
    refetchInterval: 10000
  });
  const runs = runsQuery.data?.runs ?? fallbackRuns;
  const supported = runsQuery.data?.supported ?? fallbackRuns.length > 0;
  const loaded = runsQuery.data !== undefined || fallbackRuns.length > 0;
  const commitOptions = useMemo(
    () => collectGitDiffCommitOptions(runs),
    [runs]
  );
  const selectedCommit = ensureSelectedCommit(commitOptions, selectedCommitId);
  const selectedFile = ensureSelectedFile(selectedCommit, selectedFileKey);
  const selectedFileStableKey = selectedFile ? gitDiffFileKey(selectedFile) : null;

  useEffect(() => {
    if (commitOptions.length === 0) {
      setSelectedCommitId(null);
      setSelectedFileKey(null);
      return;
    }

    const nextCommit = ensureSelectedCommit(commitOptions, selectedCommitId);
    if (nextCommit?.id !== selectedCommitId) {
      const defaultFile = selectDefaultFile(nextCommit);
      setSelectedCommitId(nextCommit?.id ?? null);
      setSelectedFileKey(defaultFile ? gitDiffFileKey(defaultFile) : null);
      return;
    }

    const nextFile = ensureSelectedFile(nextCommit, selectedFileKey);
    const nextFileKey = nextFile ? gitDiffFileKey(nextFile) : null;
    if (nextFileKey !== selectedFileKey) {
      setSelectedFileKey(nextFileKey);
    }
  }, [commitOptions, selectedCommitId, selectedFileKey]);

  useEffect(() => {
    if (!isMobileLayout) {
      setMobileStep("commits");
    }
  }, [isMobileLayout]);

  const handleEscape = useCallback(() => {
    if (isMobileLayout && mobileStep === "diff") {
      setMobileStep("files");
      return;
    }
    if (isMobileLayout && mobileStep === "files") {
      setMobileStep("commits");
      return;
    }
    onClose();
  }, [isMobileLayout, mobileStep, onClose]);

  useOverlayFocus({
    isOpen: true,
    ref: panelRef,
    onEscape: handleEscape
  });

  const handleSelectCommit = (option: GitDiffCommitOption) => {
    setSelectedCommitId(option.id);
    const file = selectDefaultFile(option);
    setSelectedFileKey(file ? gitDiffFileKey(file) : null);
    if (isMobileLayout) {
      setMobileStep("files");
    }
  };
  const handleSelectFile = (file: GitDiffFile) => {
    setSelectedFileKey(gitDiffFileKey(file));
    if (isMobileLayout) {
      setMobileStep("diff");
    }
  };
  const goBack = () => {
    if (mobileStep === "diff") {
      setMobileStep("files");
      return;
    }
    if (mobileStep === "files") {
      setMobileStep("commits");
      return;
    }
    onClose();
  };
  const title = isMobileLayout && mobileStep === "files"
    ? t("git.diff.selectFile")
    : isMobileLayout && mobileStep === "diff"
      ? t("git.diff.fileDiff")
      : t("git.diff.title");
  const subtitle = selectedCommit
    ? `${commitLabel(selectedCommit.commit)} | ${selectedCommit.runTitle}`
    : shortcutLabel;

  return (
    <div className="git-diff-browser-modal" role="dialog" aria-modal="true" aria-label={t("git.diff.browser")}>
      <section ref={panelRef} className={`git-diff-browser-panel${isMobileLayout ? " mobile" : ""}`}>
        <header className="git-diff-browser-header">
          <div>
            <strong>{title}</strong>
            <p>{subtitle}</p>
          </div>
          <div className="git-diff-browser-header-actions">
            {isMobileLayout && mobileStep !== "commits" && (
              <button
                type="button"
                className="ui-icon-button"
                aria-label={t("git.diff.back")}
                title={t("git.diff.back")}
                onClick={goBack}
              >
                <UiIcon name="chevron-left" />
              </button>
            )}
            <button
              type="button"
              className="ui-icon-button"
              aria-label={t("common.close")}
              title={t("common.close")}
              onClick={onClose}
            >
              <UiIcon name="x" />
            </button>
          </div>
        </header>
        {runsQuery.isLoading && fallbackRuns.length === 0 && <p className="muted git-diff-browser-empty">{t("git.diff.loading")}</p>}
        {runsQuery.isError && <p className="error git-diff-browser-empty" role="alert">{t("git.diff.loadFailed")}</p>}
        {loaded && !supported && (
          <p className="muted git-diff-browser-empty">
            {t("git.diff.noWorktree")}
          </p>
        )}
        {supported && commitOptions.length === 0 && (
          <p className="muted git-diff-browser-empty">{t("git.diff.noCommittedDiff")}</p>
        )}
        {supported && commitOptions.length > 0 && !isMobileLayout && (
          <div className="git-diff-browser-grid">
            <section className="git-diff-browser-column" aria-label={t("git.diff.commitSelection")}>
              <div className="git-diff-browser-column-header">
                <strong>{t("git.diff.commits")}</strong>
                <span>{commitOptions.length}</span>
              </div>
              <CommitList
                options={commitOptions}
                selectedCommitId={selectedCommit?.id ?? null}
                onSelectCommit={handleSelectCommit}
              />
            </section>
            <section className="git-diff-browser-column" aria-label={t("git.diff.fileSelection")}>
              <div className="git-diff-browser-column-header">
                <strong>{t("git.diff.files")}</strong>
                <span>{selectedCommit ? commitFileCount(selectedCommit) : 0}</span>
              </div>
              <FileList
                commitOption={selectedCommit}
                selectedFileKey={selectedFileStableKey}
                onSelectFile={handleSelectFile}
              />
            </section>
            {selectedCommit && selectedFile ? (
              <GitDiffPatchView commit={selectedCommit.commit} file={selectedFile} />
            ) : (
              <p className="muted git-diff-browser-empty">{t("git.diff.selectFilePatch")}</p>
            )}
          </div>
        )}
        {supported && commitOptions.length > 0 && isMobileLayout && (
          <div className="git-diff-browser-mobile-step">
            {mobileStep === "commits" && (
              <CommitList
                options={commitOptions}
                selectedCommitId={selectedCommit?.id ?? null}
                onSelectCommit={handleSelectCommit}
              />
            )}
            {mobileStep === "files" && (
              <FileList
                commitOption={selectedCommit}
                selectedFileKey={selectedFileStableKey}
                onSelectFile={handleSelectFile}
              />
            )}
            {mobileStep === "diff" && selectedCommit && selectedFile && (
              <GitDiffPatchView commit={selectedCommit.commit} file={selectedFile} />
            )}
          </div>
        )}
      </section>
    </div>
  );
}
