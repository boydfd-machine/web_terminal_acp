from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.terminal_runtime.application.git_worktree_coordinator.snapshot_refresh import (
    refresh_run_snapshot,
)
from app.models import ClientRuntime


class _FlushOnlySession:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


@pytest.mark.asyncio
async def test_refresh_marks_removed_worktree_merged_from_persisted_head() -> None:
    session = _FlushOnlySession()
    run = SimpleNamespace(
        command_sequence="worktree:feature",
        worktree_root="/repo/.web-terminal-acp/worktrees/window-1",
        main_repo_root="/repo",
        start_snapshot_json={
            "is_linked_worktree": True,
            "worktree_root": "/repo/.web-terminal-acp/worktrees/window-1",
            "main_repo_root": "/repo",
            "branch": "agent/feature",
            "head_sha": "base",
        },
        end_snapshot_json={
            "is_linked_worktree": True,
            "worktree_root": "/repo/.web-terminal-acp/worktrees/window-1",
            "main_repo_root": "/repo",
            "branch": "agent/feature",
            "head_sha": "feature",
            "status_porcelain": "",
            "merge_status": "unmerged",
            "merge_status_reason": "head_not_merged_to_main",
            "merged_to_main": False,
            "main_branch": "main",
            "main_head_sha": "base",
        },
        session_diff_json={},
        pending_commit=False,
        status="completed",
        resolved_at=None,
        ended_at=None,
    )

    async def fake_git_worktree_action(*_args, action: str, **payload):
        assert action == "snapshot"
        assert payload["base_head"] == "base"
        assert payload["main_repo_root"] == "/repo"
        assert payload["known_head_sha"] == "feature"
        assert payload["known_branch"] == "agent/feature"
        return {
            "ok": True,
            "snapshot": {
                "is_linked_worktree": False,
                "worktree_root": "/repo/.web-terminal-acp/worktrees/window-1",
                "main_repo_root": "/repo",
                "branch": "agent/feature",
                "head_sha": "feature",
                "status_porcelain": "",
                "diff_stat": "",
                "staged_diff_stat": "",
                "merge_status": "merged",
                "merge_status_reason": "head_is_ancestor_of_main",
                "merged_to_main": True,
                "main_branch": "main",
                "main_head_sha": "feature",
            },
        }

    async def unused_local_git_worktree_action(*_args, **_payload):
        raise AssertionError("local fallback should not be needed")

    changed = await refresh_run_snapshot(
        session,
        run,
        uuid4(),
        registry=None,
        client_runtime=ClientRuntime.local,
        git_worktree_action=fake_git_worktree_action,
        local_git_worktree_action=unused_local_git_worktree_action,
    )

    assert changed is True
    assert run.end_snapshot_json["is_linked_worktree"] is False
    assert run.end_snapshot_json["merge_status"] == "merged"
    assert run.end_snapshot_json["merged_to_main"] is True
    assert run.resolved_at is not None
    assert isinstance(run.ended_at, datetime)
    assert session.flushes == 1
