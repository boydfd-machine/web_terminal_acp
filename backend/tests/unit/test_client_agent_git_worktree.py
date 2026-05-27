from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.client_agent.git_worktree import capture_worktree_snapshot, detect_git_context


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


@pytest.mark.asyncio
async def test_linked_worktree_snapshot_uses_repo_root_and_base_head_commit_diffs(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Open Claw")
    _git(repo, "config", "user.email", "open@example.com")
    (repo / "terminal.txt").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "terminal.txt")
    _git(repo, "commit", "-m", "base")
    base_head = _git(repo, "rev-parse", "HEAD")

    worktree = tmp_path / "worktree"
    _git(repo, "worktree", "add", "-b", "agent/reload-terminal-autofocus", str(worktree))
    (worktree / "terminal.txt").write_text("new\n", encoding="utf-8")
    _git(worktree, "add", "terminal.txt")
    _git(worktree, "commit", "-m", "Fix terminal reload autofocus reconnect")

    context = await detect_git_context(str(worktree))
    snapshot = await capture_worktree_snapshot(str(worktree), base_head=base_head)

    assert context["main_repo_root"] == str(repo)
    assert snapshot["main_repo_root"] == str(repo)
    assert snapshot["head_sha"] != base_head
    assert snapshot["commits"][0]["subject"] == "Fix terminal reload autofocus reconnect"
    assert snapshot["commits"][0]["files"][0]["path"] == "terminal.txt"
    assert snapshot["commits"][0]["files"][0]["additions"] == 1
    assert snapshot["commits"][0]["files"][0]["deletions"] == 1
    assert "-old" in snapshot["commits"][0]["files"][0]["patch"]
    assert "+new" in snapshot["commits"][0]["files"][0]["patch"]
