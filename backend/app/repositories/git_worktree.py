from __future__ import annotations

import sys

from app.contexts.terminal_runtime.infrastructure import (
    git_worktree_repository as _git_worktree_repository,
)

sys.modules[__name__] = _git_worktree_repository
