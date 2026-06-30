#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from merge_agent_validation import RequiredTestSuiteError, run_required_test_suites


class MergeAgentError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _git(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"git exited {result.returncode}"
        raise MergeAgentError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return result


def _is_index_lock_error(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}"
    return "index.lock" in output and "Another git process" in output


def _git_with_index_lock_retry(
    cwd: Path,
    args: list[str],
    *,
    attempts: int = 20,
    delay_seconds: float = 0.25,
) -> subprocess.CompletedProcess[str]:
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        result = _git(cwd, args, check=False)
        if result.returncode == 0 or not _is_index_lock_error(result):
            return result
        last_result = result
        print(
            "merge-agent-branch: git index is locked, "
            f"retrying {attempt}/{attempts}: git {' '.join(args)}",
            flush=True,
        )
        time.sleep(delay_seconds)
    assert last_result is not None
    return last_result


def _repo_root(path: Path) -> Path:
    result = _git(path, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def _git_path(worktree: Path, name: str) -> Path:
    result = _git(worktree, ["rev-parse", "--path-format=absolute", name])
    return Path(result.stdout.strip()).resolve()


def _current_branch(worktree: Path) -> str:
    result = _git(worktree, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if not branch:
        raise MergeAgentError(f"{worktree} is not on a named branch")
    return branch


def _find_worktree_for_branch(repo: Path, branch: str) -> Path:
    result = _git(repo, ["worktree", "list", "--porcelain"])
    current_path: Path | None = None
    expected_ref = f"refs/heads/{branch}"
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve()
            continue
        if line == f"branch {expected_ref}" and current_path is not None:
            return current_path
    raise MergeAgentError(f"could not find a checked-out worktree for {branch}")


def _listed_worktree_branch(repo: Path, worktree: Path) -> str | None:
    result = _git(repo, ["worktree", "list", "--porcelain"])
    current_path: Path | None = None
    current_branch: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current_path == worktree:
                return current_branch
            current_path = Path(line.removeprefix("worktree ")).resolve()
            current_branch = None
            continue
        if line.startswith("branch refs/heads/"):
            current_branch = line.removeprefix("branch refs/heads/")
    if current_path == worktree:
        return current_branch
    return None


def _ensure_branch_exists(worktree: Path, branch: str) -> None:
    _git(worktree, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"])


def _active_git_operations(worktree: Path) -> list[str]:
    git_dir = _git_path(worktree, "--git-dir")
    markers = ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"]
    return [marker for marker in markers if (git_dir / marker).exists()]


def _ensure_no_git_operation(worktree: Path, label: str) -> None:
    active = _active_git_operations(worktree)
    if active:
        raise MergeAgentError(f"{label} has an active git operation: {', '.join(active)}")


def _ensure_no_non_merge_git_operation(worktree: Path, label: str) -> None:
    active = [marker for marker in _active_git_operations(worktree) if marker != "MERGE_HEAD"]
    if active:
        raise MergeAgentError(f"{label} has an active git operation: {', '.join(active)}")


def _merge_in_progress(worktree: Path) -> bool:
    return "MERGE_HEAD" in _active_git_operations(worktree)


def _status_lines(worktree: Path) -> list[str]:
    output = _git(worktree, ["status", "--porcelain=v1"]).stdout
    return [line for line in output.splitlines() if line.strip()]


def _unstaged_or_untracked_files(worktree: Path) -> list[str]:
    dirty: list[str] = []
    for line in _status_lines(worktree):
        if line.startswith("??"):
            dirty.append(line[3:] if len(line) > 3 else line)
            continue
        if len(line) >= 2 and line[1] != " ":
            dirty.append(line[3:] if len(line) > 3 else line)
    return dirty


def _ensure_clean_agent_worktree(worktree: Path) -> None:
    _ensure_no_git_operation(worktree, "agent worktree")
    status_lines = _status_lines(worktree)
    if status_lines:
        raise MergeAgentError(
            "agent worktree must be clean before merge; commit or resolve changes first:\n"
            + "\n".join(status_lines)
        )


def _ensure_agent_ready_for_landing(worktree: Path) -> None:
    _ensure_no_non_merge_git_operation(worktree, "agent worktree")
    if _merge_in_progress(worktree):
        conflicts = _unmerged_files(worktree)
        if conflicts:
            conflict_text = "\n".join(f"  {path}" for path in conflicts)
            raise MergeAgentError(
                "agent worktree still has unresolved merge conflicts. "
                "Resolve them inside the agent worktree, stage the resolutions, then rerun.\n"
                f"conflicted files:\n{conflict_text}"
            )
        dirty = _unstaged_or_untracked_files(worktree)
        if dirty:
            dirty_text = "\n".join(f"  {path}" for path in dirty)
            raise MergeAgentError(
                "agent worktree has unstaged or untracked files during a merge. "
                "Stage resolved merge files and remove unrelated files, then rerun.\n"
                f"files:\n{dirty_text}"
            )
        return
    _ensure_clean_agent_worktree(worktree)


def _ensure_main_worktree_ready(worktree: Path) -> None:
    _ensure_no_git_operation(worktree, "main worktree")


def _install_version_merge_driver(worktree: Path) -> None:
    installer = worktree / "scripts" / "install-version-merge-driver.sh"
    if installer.exists():
        result = subprocess.run(
            ["bash", str(installer)],
            cwd=worktree,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise MergeAgentError(f"version merge driver install failed: {detail}")


def _is_ancestor(worktree: Path, ancestor: str, descendant: str) -> bool:
    result = _git(worktree, ["merge-base", "--is-ancestor", ancestor, descendant], check=False)
    return result.returncode == 0


def _short_rev(worktree: Path, rev: str) -> str:
    return _git(worktree, ["rev-parse", "--short", rev]).stdout.strip()


def _unmerged_files(worktree: Path) -> list[str]:
    output = _git(worktree, ["diff", "--name-only", "--diff-filter=U"], check=False).stdout
    return [line for line in output.splitlines() if line.strip()]


def _changed_files(worktree: Path, base_ref: str, head_ref: str) -> list[str]:
    output = _git(worktree, ["diff", "--name-only", f"{base_ref}...{head_ref}"]).stdout
    return [line for line in output.splitlines() if line.strip()]


def _complete_resolved_agent_merge(worktree: Path) -> None:
    if not _merge_in_progress(worktree):
        return
    _ensure_agent_ready_for_landing(worktree)
    print("merge-agent-branch: completing resolved merge commit in agent worktree", flush=True)
    commit = _git_with_index_lock_retry(worktree, ["commit", "--no-edit"])
    print(commit.stdout, end="")
    if commit.returncode != 0:
        print(commit.stderr, end="", file=sys.stderr)
        raise MergeAgentError(
            "could not commit the resolved agent merge. "
            "Check the staged resolution in the agent worktree and rerun."
        )
    _ensure_clean_agent_worktree(worktree)


def _git_failure_detail(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or f"git exited {result.returncode}"


def _auto_cleanup_skip_reason(*, worktree: Path, main_worktree: Path, branch: str) -> str | None:
    if not branch.startswith("agent/"):
        return f"{branch} is not an agent/* branch"

    managed_worktrees_root = (main_worktree / ".web-terminal-acp" / "worktrees").resolve()
    try:
        relative_worktree = worktree.relative_to(managed_worktrees_root)
    except ValueError:
        return f"{worktree} is outside {managed_worktrees_root}"
    if not relative_worktree.parts:
        return f"{worktree} is the managed worktrees root, not a linked worktree"

    listed_branch = _listed_worktree_branch(main_worktree, worktree)
    if listed_branch is None:
        return f"{worktree} is not a linked worktree with a checked-out branch"
    if listed_branch != branch:
        return f"{worktree} is checked out on {listed_branch}, not {branch}"
    return None


def _cleanup_landed_agent_worktree(
    *,
    worktree: Path,
    main_worktree: Path,
    branch: str,
    keep_worktree: bool,
    keep_branch: bool,
) -> None:
    if keep_worktree:
        print(f"merge-agent-branch: keeping agent worktree {worktree}", flush=True)
        return

    skip_reason = _auto_cleanup_skip_reason(worktree=worktree, main_worktree=main_worktree, branch=branch)
    if skip_reason is not None:
        print(
            f"merge-agent-branch: merge succeeded, skipping automatic cleanup: {skip_reason}",
            file=sys.stderr,
            flush=True,
        )
        return

    print(f"merge-agent-branch: removing landed agent worktree {worktree}", flush=True)
    remove = _git(main_worktree, ["worktree", "remove", str(worktree)], check=False)
    if remove.returncode != 0:
        print(
            "merge-agent-branch: merge succeeded, cleanup failed: "
            f"git worktree remove {worktree} failed: {_git_failure_detail(remove)}",
            file=sys.stderr,
            flush=True,
        )
        return

    if keep_branch:
        print(f"merge-agent-branch: keeping branch {branch}", flush=True)
        return

    delete_branch = _git(main_worktree, ["branch", "-d", branch], check=False)
    if delete_branch.returncode != 0:
        print(
            "merge-agent-branch: merge succeeded, branch cleanup failed: "
            f"git branch -d {branch} failed: {_git_failure_detail(delete_branch)}",
            file=sys.stderr,
            flush=True,
        )
        return
    print(delete_branch.stdout, end="")


@contextlib.contextmanager
def _merge_lock(lock_path: Path, *, branch: str, worktree: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"merge-agent-branch: waiting for merge lock {lock_path}", flush=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        payload = {
            "pid": os.getpid(),
            "branch": branch,
            "worktree": str(worktree),
            "acquired_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(json.dumps(payload, sort_keys=True) + "\n")
        lock_file.flush()
        print("merge-agent-branch: acquired merge lock", flush=True)
        try:
            yield
        finally:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.flush()
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def merge_agent_branch(
    *,
    branch: str | None,
    worktree: Path,
    main_branch: str = "main",
    main_worktree: Path | None = None,
    pull: bool = False,
    remote: str | None = None,
    keep_worktree: bool = False,
    keep_branch: bool = False,
) -> int:
    worktree = _repo_root(worktree.resolve())
    branch = branch or _current_branch(worktree)
    if branch == main_branch:
        raise MergeAgentError("refusing to merge the main branch into itself")
    if _current_branch(worktree) != branch:
        raise MergeAgentError(f"{worktree} is on {_current_branch(worktree)}, not {branch}")
    _ensure_branch_exists(worktree, branch)
    _ensure_agent_ready_for_landing(worktree)

    main_worktree = (
        _repo_root(main_worktree.resolve())
        if main_worktree is not None
        else _find_worktree_for_branch(worktree, main_branch)
    )
    if _current_branch(main_worktree) != main_branch:
        raise MergeAgentError(f"{main_worktree} is not on {main_branch}")

    lock_path = _git_path(worktree, "--git-common-dir") / "web-terminal-acp-merge.lock"
    with _merge_lock(lock_path, branch=branch, worktree=worktree):
        _ensure_agent_ready_for_landing(worktree)
        _ensure_main_worktree_ready(main_worktree)
        _install_version_merge_driver(worktree)
        _complete_resolved_agent_merge(worktree)
        if pull:
            pull_args = ["pull", "--ff-only"]
            if remote:
                pull_args.extend([remote, main_branch])
            pull_result = _git_with_index_lock_retry(main_worktree, pull_args)
            if pull_result.returncode != 0:
                detail = pull_result.stderr.strip() or pull_result.stdout.strip()
                raise MergeAgentError(f"git {' '.join(pull_args)} failed in {main_worktree}: {detail}")
            _ensure_main_worktree_ready(main_worktree)

        if not _is_ancestor(worktree, main_branch, branch):
            before = _short_rev(worktree, branch)
            main_rev = _short_rev(worktree, main_branch)
            print(f"merge-agent-branch: merging {main_branch}@{main_rev} into {branch}@{before}")
            merge = _git_with_index_lock_retry(worktree, ["merge", "--no-edit", main_branch])
            if merge.returncode != 0:
                conflicts = _unmerged_files(worktree)
                conflict_text = "\n".join(f"  {path}" for path in conflicts) or "  <unknown>"
                print(merge.stdout, end="")
                print(merge.stderr, end="", file=sys.stderr)
                raise MergeAgentError(
                    "main changed in files that conflict with this agent branch. "
                    "Resolve the conflicts inside the agent worktree, commit, then rerun.\n"
                    f"conflicted files:\n{conflict_text}"
                )
            print(merge.stdout, end="")

        if not _is_ancestor(worktree, main_branch, branch):
            raise MergeAgentError(f"{branch} still does not contain {main_branch}")

        try:
            run_required_test_suites(
                worktree,
                _changed_files(worktree, main_branch, branch),
            )
        except RequiredTestSuiteError as exc:
            raise MergeAgentError(
                f"{exc}; fix failures and rerun before merging {branch} into {main_branch}",
                exit_code=exc.exit_code,
            ) from exc

        branch_rev = _short_rev(worktree, branch)
        print(f"merge-agent-branch: fast-forwarding {main_branch} to {branch}@{branch_rev}")
        ff = _git_with_index_lock_retry(main_worktree, ["merge", "--ff-only", branch])
        print(ff.stdout, end="")
        if ff.returncode != 0:
            print(ff.stderr, end="", file=sys.stderr)
            detail = ff.stderr.strip() or ff.stdout.strip()
            suffix = f"\n{detail}" if detail else ""
            raise MergeAgentError(
                f"could not fast-forward {main_branch}. The agent branch contains latest "
                "main; fix any main checkout changes that would be overwritten and rerun."
                + suffix
            )
        _cleanup_landed_agent_worktree(
            worktree=worktree,
            main_worktree=main_worktree,
            branch=branch,
            keep_worktree=keep_worktree,
            keep_branch=keep_branch,
        )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Merge an agent worktree branch into main behind a repo-wide file lock."
    )
    parser.add_argument("branch", nargs="?", help="agent branch to merge; defaults to current branch")
    parser.add_argument("--worktree", type=Path, default=Path.cwd(), help="agent worktree path")
    parser.add_argument("--main", default="main", help="main branch name")
    parser.add_argument("--main-worktree", type=Path, help="checked-out main worktree path")
    parser.add_argument("--pull", action="store_true", help="run git pull --ff-only on main first")
    parser.add_argument("--remote", help="remote to pull from when --pull is set")
    parser.add_argument("--keep-worktree", action="store_true", help="do not remove the landed agent worktree")
    parser.add_argument("--keep-branch", action="store_true", help="keep the landed agent branch after cleanup")
    args = parser.parse_args(argv)

    try:
        return merge_agent_branch(
            branch=args.branch,
            worktree=args.worktree,
            main_branch=args.main,
            main_worktree=args.main_worktree,
            pull=args.pull,
            remote=args.remote,
            keep_worktree=args.keep_worktree,
            keep_branch=args.keep_branch,
        )
    except MergeAgentError as exc:
        print(f"merge-agent-branch: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
