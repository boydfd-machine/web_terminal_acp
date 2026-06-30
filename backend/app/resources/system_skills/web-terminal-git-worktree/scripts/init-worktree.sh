#!/usr/bin/env bash
# Compatibility wrapper for setup-git-worktree.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/setup-git-worktree.sh" "$@"
