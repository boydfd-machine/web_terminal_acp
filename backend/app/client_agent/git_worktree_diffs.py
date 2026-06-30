from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def capture_commit_diffs(
    run_git: Callable[..., Awaitable[tuple[int, str, str]]],
    worktree_root: str,
    *,
    base_head: str | None,
    head: str = "HEAD",
) -> list[dict[str, Any]]:
    rev_range = f"{base_head}..{head}" if base_head else f"main..{head}"
    code, log_out, _stderr = await run_git(
        worktree_root,
        "log",
        "--max-count=50",
        "--date=iso-strict",
        "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s",
        "--name-status",
        rev_range,
    )
    if code != 0 or not log_out.strip():
        return []

    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in log_out.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) == 6:
            if current is not None:
                commits.append(current)
            current = {
                "sha": parts[0],
                "short_sha": parts[1],
                "author_name": parts[2],
                "author_email": parts[3],
                "authored_at": parts[4],
                "subject": parts[5],
                "files": [],
            }
            continue
        if current is None:
            continue
        file_change = _parse_name_status_line(line)
        if file_change is not None:
            current["files"].append(file_change)
    if current is not None:
        commits.append(current)

    for commit in commits:
        sha = str(commit.get("sha") or "")
        for file_change in commit["files"]:
            patch = await _capture_file_patch(
                run_git,
                worktree_root,
                sha=sha,
                path=str(file_change["path"]),
                old_path=file_change.get("old_path"),
            )
            file_change.update(patch)
    return commits


def _parse_name_status_line(line: str) -> dict[str, Any] | None:
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    raw_status = parts[0]
    code = raw_status[:1]
    if code in {"R", "C"} and len(parts) >= 3:
        return {
            "path": parts[2],
            "old_path": parts[1],
            "status": "renamed" if code == "R" else "copied",
        }
    statuses = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "T": "type_changed",
        "U": "unmerged",
    }
    return {
        "path": parts[1],
        "old_path": None,
        "status": statuses.get(code, raw_status),
    }


async def _capture_file_patch(
    run_git: Callable[..., Awaitable[tuple[int, str, str]]],
    worktree_root: str,
    *,
    sha: str,
    path: str,
    old_path: object,
) -> dict[str, Any]:
    if not sha:
        return {"patch": "", "additions": 0, "deletions": 0}
    diff_args = ["show", "--format=", "--numstat", "--patch", "--find-renames", sha, "--"]
    if isinstance(old_path, str) and old_path:
        diff_args.append(old_path)
    diff_args.append(path)
    code, output, _stderr = await run_git(worktree_root, *diff_args)
    if code != 0:
        return {"patch": "", "additions": 0, "deletions": 0}

    additions = 0
    deletions = 0
    patch_lines: list[str] = []
    in_patch = False
    for line in output.splitlines():
        if line.startswith("diff --git "):
            in_patch = True
        if not in_patch:
            fields = line.split("\t")
            if len(fields) >= 3:
                additions += _parse_numstat_count(fields[0])
                deletions += _parse_numstat_count(fields[1])
            continue
        patch_lines.append(line)
    return {
        "patch": "\n".join(patch_lines),
        "additions": additions,
        "deletions": deletions,
    }


def _parse_numstat_count(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
