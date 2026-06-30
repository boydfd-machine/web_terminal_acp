export type GitSessionDiff = {
  has_changes?: boolean;
  head_moved?: boolean;
  start_head?: string | null;
  end_head?: string | null;
  uncommitted_at_end?: boolean;
  start_status_porcelain?: string;
  end_status_porcelain?: string;
  end_diff_stat?: string;
  end_staged_diff_stat?: string;
  commits?: GitDiffCommit[];
  files?: GitDiffFileSummary[];
};

export type GitDiffFile = {
  path: string;
  old_path?: string | null;
  status?: string;
  additions?: number;
  deletions?: number;
  patch?: string;
};

export type GitDiffCommit = {
  sha: string;
  short_sha?: string;
  subject?: string;
  author_name?: string;
  author_email?: string;
  authored_at?: string;
  files?: GitDiffFile[];
};

export type GitDiffFileSummary = {
  path: string;
  old_path?: string | null;
  status?: string;
  additions?: number;
  deletions?: number;
  commits?: string[];
};

export type GitWorktreeRun = {
  id: string;
  virtual_window_id: string;
  command_sequence: string;
  agent_provider: string | null;
  status: string;
  run_type: "agent" | "tracking";
  worktree_root: string | null;
  main_repo_root: string | null;
  discovery_method: string | null;
  start_snapshot_json: Record<string, unknown> | null;
  end_snapshot_json: Record<string, unknown> | null;
  session_diff_json: GitSessionDiff | null;
  pending_commit: boolean;
  resolved_at: string | null;
  started_at: string;
  ended_at: string | null;
};

export type GitWorktreeRunList = {
  supported: boolean;
  runs: GitWorktreeRun[];
  total: number;
  limit: number;
  offset: number;
};
