from __future__ import annotations

import sys
from types import ModuleType

from app.contexts.terminal_runtime.application.git_worktree_coordinator import (
    tracking_service as _tracking_service,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.activity import (
    load_git_worktree_activity_for_window,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.refresh_lock import (
    try_acquire_window_refresh_lock,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.refresh_queries import (
    runs_for_refresh_query as _runs_for_refresh_query,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.snapshot_refresh import (
    _is_local_project_worktree_path,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.tracking_service import (
    _git_worktree_action,
    bind_worktree_for_window,
    command_needs_git_worktree_tracking,
    commands_need_git_worktree_tracking,
    git_worktree_agent_run_sequences,
    local_git_worktree_action,
    process_git_worktree_snapshot_refresh,
    process_terminal_commands_for_git,
    process_worktree_registration,
)


class _GitWorktreeCoordinatorPackage(ModuleType):
    _MIRRORED_PATCH_TARGETS = {
        "_git_worktree_action": _tracking_service,
        "local_git_worktree_action": _tracking_service,
        "try_acquire_window_refresh_lock": _tracking_service,
    }

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        module = self._MIRRORED_PATCH_TARGETS.get(name)
        if module is not None:
            setattr(module, name, value)


sys.modules[__name__].__class__ = _GitWorktreeCoordinatorPackage

__all__ = [
    "_git_worktree_action",
    "_is_local_project_worktree_path",
    "_runs_for_refresh_query",
    "bind_worktree_for_window",
    "command_needs_git_worktree_tracking",
    "commands_need_git_worktree_tracking",
    "git_worktree_agent_run_sequences",
    "load_git_worktree_activity_for_window",
    "local_git_worktree_action",
    "process_git_worktree_snapshot_refresh",
    "process_terminal_commands_for_git",
    "process_worktree_registration",
    "try_acquire_window_refresh_lock",
]
