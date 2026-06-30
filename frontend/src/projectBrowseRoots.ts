import { flattenTreeWindows } from "./terminalTree";
import type {
  GitWorktreeActivity,
  ProjectBrowseRoot,
  TreeFolder,
  VirtualWindow,
  WindowActivity
} from "./types";

export type ProjectBrowseRootOption = {
  id: string;
  kind: "main" | "worktree";
  projectPath: string;
  browseRoot: string | null;
  label: string;
  detail: string;
  searchText: string;
  pendingCommit: boolean;
};

type WorktreeSource = {
  git_worktree?: GitWorktreeActivity | null;
};

export function preferredFilesProjectContext(
  selectedWindow: WorktreeSource | null | undefined,
  fallbackProjectPath: string | null,
): { projectPath: string | null; browseRoot: string | null } {
  const gitWorktree = selectedWindow?.git_worktree ?? null;
  if (gitWorktree !== null) {
    return {
      projectPath: gitWorktree.main_repo_root,
      browseRoot: gitWorktree.worktree_root,
    };
  }
  return { projectPath: fallbackProjectPath, browseRoot: null };
}

export function buildProjectBrowseRootOptions({
  activityWindows,
  browseRoots,
  projectPath,
  selectedWindow,
  treeFolders,
}: {
  activityWindows?: Array<WindowActivity & { window_id: string }> | null;
  browseRoots?: ProjectBrowseRoot[] | null;
  projectPath: string | null;
  selectedWindow?: (VirtualWindow | WorktreeSource) | null;
  treeFolders?: TreeFolder[] | null;
}): ProjectBrowseRootOption[] {
  const sources = collectWorktreeSources({ activityWindows, selectedWindow, treeFolders });
  const projectRoot = projectRootForContext(projectPath, sources, browseRoots);
  if (projectRoot === null) {
    return [];
  }

  const options = new Map<string, ProjectBrowseRootOption>();
  const rootsForProject = (browseRoots ?? []).filter((root) => (
    root.project_path === projectRoot || root.browse_root === projectRoot
  ));
  const mainProjectRoot = rootsForProject.find((root) => root.kind === "main")?.project_path ?? projectRoot;
  const mainOption = optionForMainRoot(mainProjectRoot);
  options.set(mainOption.id, mainOption);
  for (const root of rootsForProject) {
    const option = optionForBrowseRoot(root);
    options.set(option.id, option);
  }
  for (const source of sources) {
    const worktree = source.git_worktree ?? null;
    if (worktree === null || worktree.main_repo_root !== mainProjectRoot) {
      continue;
    }
    const option = optionForWorktree(worktree);
    options.set(option.id, option);
  }

  return Array.from(options.values()).sort((left, right) => {
    if (left.kind !== right.kind) {
      return left.kind === "main" ? -1 : 1;
    }
    return left.label.localeCompare(right.label) || left.detail.localeCompare(right.detail);
  });
}

function collectWorktreeSources({
  activityWindows,
  selectedWindow,
  treeFolders,
}: {
  activityWindows?: Array<WindowActivity & { window_id: string }> | null;
  selectedWindow?: (VirtualWindow | WorktreeSource) | null;
  treeFolders?: TreeFolder[] | null;
}): WorktreeSource[] {
  return [
    selectedWindow ?? null,
    ...(activityWindows ?? []),
    ...flattenTreeWindows(treeFolders ?? undefined),
  ].filter((source): source is WorktreeSource => source !== null && source !== undefined);
}

function projectRootForContext(
  projectPath: string | null,
  sources: WorktreeSource[],
  browseRoots?: ProjectBrowseRoot[] | null,
): string | null {
  if (projectPath === null) {
    return browseRoots?.[0]?.project_path ?? sources[0]?.git_worktree?.main_repo_root ?? null;
  }
  const matchingBrowseRoot = (browseRoots ?? []).find((root) => (
    root.project_path === projectPath || root.browse_root === projectPath
  ));
  if (matchingBrowseRoot !== undefined) {
    return matchingBrowseRoot.project_path;
  }
  const matchingWorktree = sources
    .map((source) => source.git_worktree ?? null)
    .find((worktree) => (
      worktree !== null
      && (worktree.main_repo_root === projectPath || worktree.worktree_root === projectPath)
    ));
  return matchingWorktree?.main_repo_root ?? projectPath;
}

function optionForMainRoot(projectPath: string): ProjectBrowseRootOption {
  const label = "no-worktree [main directory]";
  return {
    id: "no-worktree",
    kind: "main",
    projectPath,
    browseRoot: null,
    label,
    detail: projectPath,
    searchText: `${label} ${projectPath}`.toLocaleLowerCase(),
    pendingCommit: false,
  };
}

function optionForBrowseRoot(root: ProjectBrowseRoot): ProjectBrowseRootOption {
  if (root.kind === "main") {
    return optionForMainRoot(root.project_path);
  }
  const browseRoot = root.browse_root ?? root.project_path;
  const branch = root.branch?.trim() || "(detached)";
  const label = branch;
  return {
    id: `worktree:${browseRoot}`,
    kind: "worktree",
    projectPath: root.project_path,
    browseRoot,
    label,
    detail: browseRoot,
    searchText: `${branch} ${browseRoot} ${root.project_path}`.toLocaleLowerCase(),
    pendingCommit: root.pending_commit,
  };
}

function optionForWorktree(worktree: GitWorktreeActivity): ProjectBrowseRootOption {
  const branch = worktree.branch?.trim() || "(detached)";
  const label = branch;
  return {
    id: `worktree:${worktree.worktree_root}`,
    kind: "worktree",
    projectPath: worktree.main_repo_root,
    browseRoot: worktree.worktree_root,
    label,
    detail: worktree.worktree_root,
    searchText: `${branch} ${worktree.worktree_root} ${worktree.main_repo_root}`.toLocaleLowerCase(),
    pendingCommit: worktree.pending_commit,
  };
}
