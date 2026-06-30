#!/usr/bin/env bash
# Remove this terminal's Web Terminal worktree (run from main checkout).
set -euo pipefail

if [[ -z "${WEB_TERMINAL_WINDOW_ID:-}" ]]; then
  echo "remove-worktree: WEB_TERMINAL_WINDOW_ID is not set" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "remove-worktree: not inside a git repository" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
git_common_dir="$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir)"
main_root="$(
  WEB_TERMINAL_GIT_COMMON_DIR="$git_common_dir" python3 - <<'PY'
import os
from pathlib import Path

common_dir = Path(os.environ["WEB_TERMINAL_GIT_COMMON_DIR"]).expanduser().resolve()
if common_dir.name == ".git":
    print(common_dir.parent)
else:
    print(common_dir)
PY
)"
cd "$main_root"

wt_rel=".web-terminal-acp/worktrees/${WEB_TERMINAL_WINDOW_ID}"
if [[ ! -d "$wt_rel" ]]; then
  echo "remove-worktree: no worktree at $wt_rel" >&2
  exit 0
fi

branch="$(git -C "$wt_rel" branch --show-current 2>/dev/null || true)"
git worktree remove --force "$wt_rel" 2>/dev/null || git worktree remove "$wt_rel"

if [[ -n "$branch" ]] && git show-ref --verify --quiet "refs/heads/$branch"; then
  git branch -d "$branch" 2>/dev/null || echo "remove-worktree: branch $branch not deleted (may be unmerged)" >&2
fi

echo "Removed worktree: $wt_rel"
