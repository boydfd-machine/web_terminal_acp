from __future__ import annotations

import subprocess
import asyncio
from pathlib import Path

import pytest

from app.client_agent.git_worktree import capture_worktree_snapshot, detect_git_context
import app.client_agent.git_worktree as git_worktree


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
    assert snapshot["merge_status"] == "unmerged"
    assert snapshot["merged_to_main"] is False


@pytest.mark.asyncio
async def test_linked_worktree_snapshot_detects_merge_back_to_main(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Open Claw")
    _git(repo, "config", "user.email", "open@example.com")
    (repo / "terminal.txt").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "terminal.txt")
    _git(repo, "commit", "-m", "base")

    worktree = tmp_path / "worktree"
    _git(repo, "worktree", "add", "-b", "agent/merge-done", str(worktree))
    (worktree / "terminal.txt").write_text("new\n", encoding="utf-8")
    _git(worktree, "commit", "-am", "Fix terminal")
    _git(repo, "merge", "--ff-only", "agent/merge-done")

    snapshot = await capture_worktree_snapshot(str(worktree))

    assert snapshot["merge_status"] == "merged"
    assert snapshot["merged_to_main"] is True


@pytest.mark.asyncio
async def test_removed_worktree_snapshot_detects_merge_from_known_head(tmp_path) -> None:
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
    _git(repo, "worktree", "add", "-b", "agent/cleanup", str(worktree))
    (worktree / "terminal.txt").write_text("new\n", encoding="utf-8")
    _git(worktree, "commit", "-am", "Fix terminal merge label")
    feature_head = _git(worktree, "rev-parse", "HEAD")
    _git(repo, "merge", "--ff-only", "agent/cleanup")
    _git(repo, "worktree", "remove", str(worktree))
    _git(repo, "branch", "-d", "agent/cleanup")

    snapshot = await capture_worktree_snapshot(
        str(worktree),
        base_head=base_head,
        main_repo_root=str(repo),
        known_head_sha=feature_head,
        known_branch="agent/cleanup",
    )

    assert snapshot["is_linked_worktree"] is False
    assert snapshot["worktree_root"] == str(worktree)
    assert snapshot["main_repo_root"] == str(repo)
    assert snapshot["branch"] == "agent/cleanup"
    assert snapshot["head_sha"] == feature_head
    assert snapshot["commits"][0]["subject"] == "Fix terminal merge label"
    assert snapshot["merge_status"] == "merged"
    assert snapshot["merged_to_main"] is True


@pytest.mark.asyncio
async def test_linked_worktree_snapshot_detects_main_merge_conflict(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Open Claw")
    _git(repo, "config", "user.email", "open@example.com")
    (repo / "terminal.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "terminal.txt")
    _git(repo, "commit", "-m", "base")

    worktree = tmp_path / "worktree"
    _git(repo, "worktree", "add", "-b", "agent/conflict", str(worktree))
    (worktree / "terminal.txt").write_text("agent\n", encoding="utf-8")
    _git(worktree, "commit", "-am", "Agent change")
    (repo / "terminal.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "commit", "-am", "Main change")
    merge = subprocess.run(
        ["git", "merge", "agent/conflict"],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert merge.returncode != 0

    snapshot = await capture_worktree_snapshot(str(worktree))

    assert snapshot["merge_status"] == "conflict"
    assert snapshot["merged_to_main"] is False
    assert snapshot["main_merge_in_progress"] is True
    assert snapshot["main_merge_matches_worktree"] is True
    assert snapshot["unmerged_files"] == ["terminal.txt"]


@pytest.mark.asyncio
async def test_run_git_timeout_handles_process_already_exited_race(monkeypatch, tmp_path) -> None:
    class ExitedDuringTimeoutProcess:
        returncode = None

        async def communicate(self):
            await asyncio.Event().wait()

        def kill(self) -> None:
            raise ProcessLookupError()

        async def wait(self) -> None:
            return None

    async def fake_create_subprocess_exec(*args, **kwargs):
        return ExitedDuringTimeoutProcess()

    monkeypatch.setattr(git_worktree, "_GIT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(git_worktree.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    code, stdout, stderr = await git_worktree._run_git(str(tmp_path), "status")

    assert (code, stdout, stderr) == (124, "", "git command timed out")
