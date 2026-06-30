from __future__ import annotations

import subprocess
import sys
import time
from multiprocessing import Event, Process, Queue
from pathlib import Path
from queue import Empty

from tests.unit.merge_agent_branch_test_support import (
    SCRIPT_PATH,
    _commit,
    _git,
    _init_repo,
    merge_agent_branch,
)


def test_conflict_is_left_in_agent_worktree_and_main_is_unchanged(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "file.txt").write_text("agent\n", encoding="utf-8")
    _commit(agent, "agent change")
    (main / "file.txt").write_text("main\n", encoding="utf-8")
    main_head = _commit(main, "main change")

    try:
        merge_agent_branch.merge_agent_branch(
            branch="agent/feature",
            worktree=agent,
            main_worktree=main,
        )
    except merge_agent_branch.MergeAgentError as exc:
        assert "conflicted files" in str(exc)
    else:
        raise AssertionError("expected merge conflict")

    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == main_head
    assert _git(agent, "diff", "--name-only", "--diff-filter=U").stdout.strip() == "file.txt"


def test_rerun_commits_resolved_agent_merge_and_fast_forwards_main(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "file.txt").write_text("agent\n", encoding="utf-8")
    _commit(agent, "agent change")
    (main / "file.txt").write_text("main\n", encoding="utf-8")
    _commit(main, "main change")
    try:
        merge_agent_branch.merge_agent_branch(
            branch="agent/feature",
            worktree=agent,
            main_worktree=main,
        )
    except merge_agent_branch.MergeAgentError:
        pass
    else:
        raise AssertionError("expected merge conflict")

    (agent / "file.txt").write_text("resolved\n", encoding="utf-8")
    _git(agent, "add", "file.txt")

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert _git(agent, "diff", "--name-only", "--diff-filter=U").stdout == ""
    assert _git(agent, "status", "--porcelain=v1").stdout == ""
    assert (main / "file.txt").read_text(encoding="utf-8") == "resolved\n"
    assert _git(main, "rev-parse", "HEAD").stdout == _git(agent, "rev-parse", "HEAD").stdout


def _hold_lock(lock_path: str, ready: Event, release: Event) -> None:
    with merge_agent_branch._merge_lock(
        Path(lock_path),
        branch="agent/one",
        worktree=Path("/tmp/agent-one"),
    ):
        ready.set()
        release.wait(5)


def _try_lock(lock_path: str, acquired: Queue[str]) -> None:
    with merge_agent_branch._merge_lock(
        Path(lock_path),
        branch="agent/two",
        worktree=Path("/tmp/agent-two"),
    ):
        acquired.put("acquired")


def test_merge_lock_blocks_other_processes_until_released(tmp_path: Path) -> None:
    lock_path = tmp_path / "merge.lock"
    ready = Event()
    release = Event()
    holder = Process(target=_hold_lock, args=(str(lock_path), ready, release))
    contender_queue: Queue[str] = Queue()
    contender = Process(target=_try_lock, args=(str(lock_path), contender_queue))

    holder.start()
    try:
        assert ready.wait(5)
        contender.start()
        time.sleep(0.2)
        try:
            contender_queue.get_nowait()
        except Empty:
            pass
        else:
            raise AssertionError("second process acquired lock before release")

        release.set()
        contender.join(5)
        assert contender.exitcode == 0
        assert contender_queue.get(timeout=1) == "acquired"
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
        if contender.is_alive():
            contender.terminate()


def test_git_with_index_lock_retry_waits_for_transient_lock(monkeypatch) -> None:
    calls = 0

    def fake_git(cwd: Path, args: list[str], *, check: bool = True):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                ["git", *args],
                128,
                "",
                "Unable to create '.git/index.lock': File exists.\nAnother git process seems to be running in this repository.\n",
            )
        return subprocess.CompletedProcess(["git", *args], 0, "ok\n", "")

    monkeypatch.setattr(merge_agent_branch, "_git", fake_git)
    monkeypatch.setattr(merge_agent_branch.time, "sleep", lambda _seconds: None)

    result = merge_agent_branch._git_with_index_lock_retry(Path("/repo"), ["merge", "--ff-only", "agent/x"])

    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert calls == 2


def test_cli_reports_conflict_exit_code(tmp_path: Path) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "file.txt").write_text("agent\n", encoding="utf-8")
    _commit(agent, "agent change")
    (main / "file.txt").write_text("main\n", encoding="utf-8")
    _commit(main, "main change")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "agent/feature",
            "--worktree",
            str(agent),
            "--main-worktree",
            str(main),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "conflicted files" in result.stderr
