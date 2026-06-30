import type { GitWorktreeRun } from "./git";

export type ProjectTodoWorktreeFile = {
  path: string;
  old_path?: string | null;
  status?: string | null;
  additions?: number | null;
  deletions?: number | null;
};

export type ProjectTodoWorktreeCommit = {
  sha?: string | null;
  short_sha?: string | null;
  subject?: string | null;
  author_name?: string | null;
  authored_at?: string | null;
  files?: ProjectTodoWorktreeFile[];
};

export type ProjectTodoWorktree = {
  window_id?: string | null;
  main_repo_root?: string | null;
  worktree_root?: string | null;
  branch?: string | null;
  start_head?: string | null;
  end_head?: string | null;
  has_changes?: boolean;
  pending_commit?: boolean;
  merge_status?: "merged" | "unmerged" | "conflict" | "unknown";
  merge_status_reason?: string | null;
  merged_to_main?: boolean | null;
  merge_attention_required?: boolean;
  main_branch?: string | null;
  main_head_sha?: string | null;
  main_merge_head_sha?: string | null;
  main_merge_in_progress?: boolean;
  main_merge_matches_worktree?: boolean | null;
  unmerged_files?: string[];
  runs_total?: number;
  commits?: ProjectTodoWorktreeCommit[];
  files?: ProjectTodoWorktreeFile[];
  diff_runs?: GitWorktreeRun[];
  captured_at?: string | null;
};
