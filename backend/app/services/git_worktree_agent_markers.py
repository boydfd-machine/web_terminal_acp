from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import (
    git_worktree_agent_markers as _git_worktree_agent_markers,
)

sys.modules[__name__] = _git_worktree_agent_markers
