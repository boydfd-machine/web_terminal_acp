import { useI18n, type TranslateFn } from "../i18n";

type GitMergeStatusSource = {
  main_branch?: string | null;
  main_merge_in_progress?: boolean;
  merge_attention_required?: boolean;
  merge_status?: "merged" | "unmerged" | "conflict" | "unknown";
  merge_status_reason?: string | null;
  merged_to_main?: boolean | null;
  unmerged_files?: string[];
};

export function gitMergeAttentionRequired(source: GitMergeStatusSource | null | undefined): boolean {
  return (
    source?.merge_attention_required === true
    || source?.merge_status === "conflict"
    || source?.merge_status === "unmerged"
    || source?.merged_to_main === false
  );
}

export function gitMergeStatusLabel(source: GitMergeStatusSource | null | undefined, t?: TranslateFn): string {
  if (source?.merge_status === "conflict") {
    return t?.("git.merge.conflict") ?? "Merge conflict";
  }
  if (source?.merge_status === "unmerged" || source?.merged_to_main === false) {
    return t?.("git.merge.notMerged") ?? "Not merged";
  }
  if (source?.merge_status === "merged" || source?.merged_to_main === true) {
    return t?.("git.merge.merged") ?? "Merged";
  }
  return t?.("git.merge.unknown") ?? "Unknown";
}

export function gitMergeStatusDetail(source: GitMergeStatusSource | null | undefined, t?: TranslateFn): string {
  const mainBranch = source?.main_branch ?? "main";
  if (source?.merge_status === "conflict") {
    const files = source.unmerged_files?.slice(0, 3).join(", ");
    return files
      ? t?.("git.merge.conflictWithFiles", { branch: mainBranch, files }) ?? `Merge into ${mainBranch} has conflicts: ${files}`
      : t?.("git.merge.conflictNoFiles", { branch: mainBranch }) ?? `Merge into ${mainBranch} has conflicts`;
  }
  if (source?.main_merge_in_progress) {
    return t?.("git.merge.inProgress", { branch: mainBranch }) ?? `Merge into ${mainBranch} is still in progress`;
  }
  if (source?.merge_status === "unmerged" || source?.merged_to_main === false) {
    return t?.("git.merge.notMergedDetail", { branch: mainBranch }) ?? `Worktree branch is not merged into ${mainBranch}`;
  }
  if (source?.merge_status === "merged" || source?.merged_to_main === true) {
    return t?.("git.merge.mergedDetail", { branch: mainBranch }) ?? `Worktree branch is merged into ${mainBranch}`;
  }
  return t?.("git.merge.unknownDetail") ?? "Merge status unknown";
}

export function GitMergeStatusBadge({
  source,
  compact = false
}: {
  source: GitMergeStatusSource | null | undefined;
  compact?: boolean;
}) {
  const { t } = useI18n();

  if (!gitMergeAttentionRequired(source)) {
    return null;
  }
  const label = gitMergeStatusLabel(source, t);
  const status = source?.merge_status === "conflict" ? "conflict" : "unmerged";
  return (
    <span
      className={`git-merge-status-badge ${status}${compact ? " compact" : ""}`}
      title={gitMergeStatusDetail(source, t)}
      aria-label={label}
    >
      {compact ? "Git" : label}
    </span>
  );
}
