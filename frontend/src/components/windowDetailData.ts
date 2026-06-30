import type { SummaryJob, TerminalArtifact, TreeFolderCore, VirtualWindow } from "../types";
import type { TranslateFn } from "../i18n";

export type SummaryStatus = {
  label: string;
  tone?: "muted" | "error";
};
export type AgentDetailTab = "record" | "config";
export type HistoryDetailTab = "commands" | "title";

export const COMMAND_HISTORY_PAGE_SIZE = 100;
export const TITLE_HISTORY_PAGE_SIZE = 100;
export const ARTIFACT_PAGE_SIZE = 50;
export const MAX_TITLE_LENGTH = 255;
export const PATH_HEAD_LENGTH = 18;
export const PATH_TAIL_LENGTH = 30;

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function summaryStatus(
  summaryJob: SummaryJob | null,
  commandCaptureSupported: boolean,
  t?: TranslateFn
): SummaryStatus {
  if (!commandCaptureSupported) {
    return { label: t?.("window.summary.unsupportedShell") ?? "unsupported shell", tone: "muted" };
  }

  if (summaryJob === null) {
    return { label: t?.("window.summary.noJob") ?? "No summary job yet.", tone: "muted" };
  }

  switch (summaryJob.status.toUpperCase()) {
    case "PENDING":
      return summaryJob.run_after
        ? {
            label: t?.("window.summary.waitingUntil", { time: formatDateTime(summaryJob.run_after) })
              ?? `waiting until ${formatDateTime(summaryJob.run_after)}`
          }
        : { label: t?.("window.summary.waiting") ?? "waiting" };
    case "RUNNING":
      return { label: t?.("window.summary.running") ?? "running" };
    case "SUCCEEDED":
      return { label: t?.("window.summary.succeeded") ?? "succeeded" };
    case "FAILED":
      return { label: t?.("window.summary.failed") ?? "failed", tone: "error" };
    default:
      return { label: summaryJob.status.toLowerCase() };
  }
}
export function displayTags(item: VirtualWindow): string[] {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const tag of item.title_tags ?? []) {
    const normalized = tag.trim();
    const key = normalized.toLocaleLowerCase();
    if (!normalized || seen.has(key)) {
      continue;
    }
    seen.add(key);
    tags.push(normalized);
  }
  return tags;
}

export function compactPath(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  if (value.length <= PATH_HEAD_LENGTH + PATH_TAIL_LENGTH + 5) {
    return value;
  }

  return `${value.slice(0, PATH_HEAD_LENGTH)}/.../${value.slice(-PATH_TAIL_LENGTH)}`;
}
export function artifactStatusLabel(artifact: TerminalArtifact, t?: TranslateFn): string {
  switch (artifact.status.toUpperCase()) {
    case "PENDING":
      return t?.("artifacts.status.pending") ?? "pending";
    case "RUNNING":
      return t?.("artifacts.status.running") ?? "running";
    case "SUCCEEDED":
      return t?.("artifacts.status.ready") ?? "ready";
    case "FAILED":
      return t?.("artifacts.status.failed") ?? "failed";
    default:
      return artifact.status.toLowerCase();
  }
}

export function artifactKindLabel(kind: string, t?: TranslateFn): string {
  if (kind === "page_review_cards") {
    return t?.("artifacts.kind.pageReviewCards") ?? "Page Review Cards";
  }
  return kind
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function renameTreeWindow(
  folders: TreeFolderCore[] | undefined,
  windowId: string,
  title: string
): TreeFolderCore[] | undefined {
  if (folders === undefined) {
    return undefined;
  }

  let changed = false;
  const nextFolders = folders.map((folder) => {
    let folderChanged = false;
    const windows = folder.windows.map((window) => {
      if (window.id !== windowId) {
        return window;
      }

      folderChanged = true;
      return { ...window, title };
    });
    const childFolders = renameTreeWindow(folder.folders, windowId, title);
    if (childFolders !== folder.folders) {
      folderChanged = true;
    }
    if (!folderChanged) {
      return folder;
    }

    changed = true;
    return { ...folder, folders: childFolders ?? folder.folders, windows };
  });

  return changed ? nextFolders : folders;
}
