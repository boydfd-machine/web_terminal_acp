from __future__ import annotations

import sys

from app.contexts.terminal_runtime.domain import git_worktree_ops as _git_worktree_ops

sys.modules[__name__] = _git_worktree_ops
