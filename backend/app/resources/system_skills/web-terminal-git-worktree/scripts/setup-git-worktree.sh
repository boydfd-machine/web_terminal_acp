#!/usr/bin/env bash
# Create a Web Terminal worktree, register it, and seed backend/frontend dependencies.
# Usage: setup-git-worktree.sh [branch-suffix] [--frontend|--backend]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${WEB_TERMINAL_WINDOW_ID:-}" ]]; then
  echo "setup-git-worktree: WEB_TERMINAL_WINDOW_ID is not set (not a Web Terminal shell?)" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "setup-git-worktree: current directory is not inside a git repository" >&2
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

branch_suffix="${WEB_TERMINAL_WINDOW_ID:0:8}"
dependency_mode="both"
dependency_mode_set=false
branch_suffix_set=false

while (($#)); do
  case "$1" in
    --frontend)
      if [[ "$dependency_mode_set" == true ]]; then
        echo "setup-git-worktree: --frontend and --backend cannot be combined" >&2
        exit 1
      fi
      dependency_mode="frontend"
      dependency_mode_set=true
      shift
      ;;
    --backend)
      if [[ "$dependency_mode_set" == true ]]; then
        echo "setup-git-worktree: --frontend and --backend cannot be combined" >&2
        exit 1
      fi
      dependency_mode="backend"
      dependency_mode_set=true
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: setup-git-worktree.sh [branch-suffix] [--frontend|--backend]
EOF
      exit 0
      ;;
    -*)
      echo "setup-git-worktree: unknown option: $1" >&2
      exit 1
      ;;
    *)
      if [[ "$branch_suffix_set" == true ]]; then
        echo "setup-git-worktree: branch suffix already set to $branch_suffix" >&2
        exit 1
      fi
      branch_suffix="$1"
      branch_suffix_set=true
      shift
      ;;
  esac
done

branch="agent/${branch_suffix}"
wt_rel=".web-terminal-acp/worktrees/${WEB_TERMINAL_WINDOW_ID}"
wt_abs="${main_root}/${wt_rel}"

if [[ -d "$wt_abs" && ! -f "$wt_abs/.git" ]]; then
  echo "setup-git-worktree: worktree path exists but is not a linked worktree: $wt_abs" >&2
  exit 1
fi

if [[ ! -d "$wt_abs" ]]; then
  if [[ -f "$repo_root/.git" ]]; then
    echo "setup-git-worktree: already inside a linked worktree; using $repo_root" >&2
    wt_abs="$repo_root"
  else
    if [[ ! -d "$repo_root/.git" ]]; then
      echo "setup-git-worktree: current git checkout is not a main repository checkout" >&2
      exit 1
    fi
    cd "$main_root"
    mkdir -p "$(dirname "$wt_rel")"
    git worktree add "$wt_rel" -b "$branch"
  fi
fi

cd "$wt_abs"
bash "$SCRIPT_DIR/register-worktree.sh"

copy_tree() {
  local label="$1"
  local source="$2"
  local destination="$3"

  if [[ ! -d "$source" ]]; then
    echo "setup-git-worktree: skipping $label because source is missing: $source"
    return 0
  fi

  mkdir -p "$(dirname "$destination")"
  rm -rf "$destination"
  cp -a "$source" "$destination"
  echo "setup-git-worktree: copying $label from main checkout"
}

if [[ "$dependency_mode" == "both" || "$dependency_mode" == "backend" ]]; then
  copy_tree "backend .venv" "$main_root/backend/.venv" "$wt_abs/backend/.venv"
fi

if [[ "$dependency_mode" == "both" || "$dependency_mode" == "frontend" ]]; then
  copy_tree "frontend node_modules" "$main_root/frontend/node_modules" "$wt_abs/frontend/node_modules"
fi
