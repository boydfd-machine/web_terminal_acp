from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.merge_agent_branch_test_support import (
    _branch_exists,
    _commit,
    _git,
    _init_managed_repo,
    _init_repo,
    _run_cli,
    _worktree_list,
    merge_agent_branch,
)


def test_fast_forwards_main_when_branch_already_contains_main(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert _git(main, "status", "--porcelain=v1").stdout == ""


def test_default_cleanup_removes_managed_agent_worktree_and_branch(tmp_path: Path) -> None:
    main, agent = _init_managed_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert not agent.exists()
    assert str(agent) not in _worktree_list(main)
    assert not _branch_exists(main, "agent/feature")


def test_keep_worktree_option_preserves_managed_worktree_and_branch(tmp_path: Path) -> None:
    main, agent = _init_managed_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")

    result = _run_cli(
        "agent/feature",
        "--worktree",
        str(agent),
        "--main-worktree",
        str(main),
        "--keep-worktree",
    )

    assert result.returncode == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert agent.exists()
    assert str(agent) in _worktree_list(main)
    assert _branch_exists(main, "agent/feature")


def test_keep_branch_option_removes_managed_worktree_but_preserves_branch(tmp_path: Path) -> None:
    main, agent = _init_managed_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
        keep_branch=True,
    )

    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert not agent.exists()
    assert str(agent) not in _worktree_list(main)
    assert _branch_exists(main, "agent/feature")


def test_cleanup_failure_reports_but_merge_remains_successful(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    main, agent = _init_managed_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")
    original_git = merge_agent_branch._git
    branch_delete_calls: list[list[str]] = []

    def fake_git(cwd: Path, args: list[str], *, check: bool = True):
        if args[:2] == ["worktree", "remove"]:
            return subprocess.CompletedProcess(
                ["git", *args],
                1,
                "",
                "fatal: worktree contains modified or untracked files\n",
            )
        if args[:2] == ["branch", "-d"]:
            branch_delete_calls.append(args)
        return original_git(cwd, args, check=check)

    monkeypatch.setattr(merge_agent_branch, "_git", fake_git)

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    captured = capsys.readouterr()
    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert "merge succeeded, cleanup failed" in captured.err
    assert agent.exists()
    assert _branch_exists(main, "agent/feature")
    assert branch_delete_calls == []


def test_branch_cleanup_uses_safe_delete_and_failure_does_not_roll_back(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    main, agent = _init_managed_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")
    original_git = merge_agent_branch._git
    branch_delete_calls: list[list[str]] = []

    def fake_git(cwd: Path, args: list[str], *, check: bool = True):
        if args == ["branch", "-d", "agent/feature"]:
            branch_delete_calls.append(args)
            return subprocess.CompletedProcess(
                ["git", *args],
                1,
                "",
                "error: the branch 'agent/feature' is not fully merged\n",
            )
        return original_git(cwd, args, check=check)

    monkeypatch.setattr(merge_agent_branch, "_git", fake_git)

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    captured = capsys.readouterr()
    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert branch_delete_calls == [["branch", "-d", "agent/feature"]]
    assert "merge succeeded, branch cleanup failed" in captured.err
    assert not agent.exists()
    assert _branch_exists(main, "agent/feature")


def test_default_cleanup_refuses_non_managed_worktree(tmp_path: Path, capsys) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    captured = capsys.readouterr()
    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert "skipping automatic cleanup" in captured.err
    assert "outside" in captured.err
    assert agent.exists()
    assert _branch_exists(main, "agent/feature")


def test_fast_forwards_main_with_unrelated_local_main_changes(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    branch_head = _commit(agent, "feature")
    (main / "local.txt").write_text("local\n", encoding="utf-8")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == branch_head
    assert (main / "local.txt").read_text(encoding="utf-8") == "local\n"
    assert _git(main, "status", "--porcelain=v1").stdout.strip() == "?? local.txt"


def test_overlapping_local_main_changes_block_fast_forward(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "file.txt").write_text("agent\n", encoding="utf-8")
    _commit(agent, "agent change")
    main_head = _git(main, "rev-parse", "--short", "HEAD").stdout.strip()
    (main / "file.txt").write_text("local\n", encoding="utf-8")

    try:
        merge_agent_branch.merge_agent_branch(
            branch="agent/feature",
            worktree=agent,
            main_worktree=main,
        )
    except merge_agent_branch.MergeAgentError as exc:
        assert "would be overwritten" in str(exc)
    else:
        raise AssertionError("expected local main change to block fast-forward")

    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == main_head
    assert (main / "file.txt").read_text(encoding="utf-8") == "local\n"


def test_merges_current_main_in_agent_worktree_before_fast_forward(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "feature.txt").write_text("feature\n", encoding="utf-8")
    _commit(agent, "feature")
    (main / "main.txt").write_text("main\n", encoding="utf-8")
    main_head = _commit(main, "main change")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(agent, "merge-base", "--is-ancestor", main_head, "agent/feature").returncode == 0
    assert _git(main, "rev-parse", "HEAD").stdout == _git(agent, "rev-parse", "HEAD").stdout
    assert (main / "feature.txt").read_text(encoding="utf-8") == "feature\n"


def test_installs_version_merge_driver_before_landing(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    scripts_dir = agent / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "install-version-merge-driver.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "git config --local test.merge-driver-installed true\n",
        encoding="utf-8",
    )
    _commit(agent, "add merge driver installer")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(agent, "config", "--local", "--get", "test.merge-driver-installed").stdout.strip() == "true"
