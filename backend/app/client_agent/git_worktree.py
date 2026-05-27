from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

_GIT_TIMEOUT_SECONDS = 2.0


async def _run_git(cwd: str, *args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=_GIT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return 124, "", "git command timed out"
    return (
        process.returncode or 0,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )


def _normalize_path(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def is_linked_worktree_path(path: str) -> bool:
    git_entry = Path(path) / ".git"
    return git_entry.is_file()


def _main_repo_root_from_worktree_gitdir(gitdir: str) -> str | None:
    common_dir = Path(gitdir).parent.parent
    if common_dir.name == ".git":
        return _normalize_path(str(common_dir.parent))
    return _normalize_path(str(common_dir))


async def detect_git_context(path: str) -> dict[str, Any]:
    normalized = _normalize_path(path)
    if not os.path.isdir(normalized):
        return {"is_git": False, "is_linked_worktree": False, "path": normalized}

    code, inside, _stderr = await _run_git(normalized, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside.lower() != "true":
        return {"is_git": False, "is_linked_worktree": False, "path": normalized}

    is_linked = is_linked_worktree_path(normalized)
    _code, top_level, _stderr = await _run_git(normalized, "rev-parse", "--show-toplevel")
    worktree_root = _normalize_path(top_level) if top_level else normalized

    main_repo_root: str | None = None
    branch: str | None = None
    head_sha: str | None = None

    if is_linked:
        git_file = Path(worktree_root) / ".git"
        try:
            gitdir_line = git_file.read_text(encoding="utf-8").strip()
            if gitdir_line.startswith("gitdir: "):
                gitdir = _normalize_path(gitdir_line.removeprefix("gitdir: ").strip())
                main_repo_root = _main_repo_root_from_worktree_gitdir(gitdir)
        except OSError:
            main_repo_root = None
    else:
        main_repo_root = worktree_root

    _code, branch_out, _stderr = await _run_git(worktree_root, "branch", "--show-current")
    if branch_out:
        branch = branch_out

    _code, head_out, _stderr = await _run_git(worktree_root, "rev-parse", "HEAD")
    if head_out:
        head_sha = head_out

    return {
        "is_git": True,
        "is_linked_worktree": is_linked,
        "path": normalized,
        "worktree_root": worktree_root,
        "main_repo_root": main_repo_root,
        "branch": branch,
        "head_sha": head_sha,
    }


async def list_worktrees(main_repo_root: str) -> list[str]:
    code, stdout, _stderr = await _run_git(main_repo_root, "worktree", "list", "--porcelain")
    if code != 0:
        return []

    paths: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(_normalize_path(line.removeprefix("worktree ").strip()))
    return paths


async def capture_worktree_snapshot(worktree_root: str, *, base_head: str | None = None) -> dict[str, Any]:
    context = await detect_git_context(worktree_root)
    if not context.get("is_linked_worktree"):
        return {"is_linked_worktree": False, "worktree_root": worktree_root}

    root = context["worktree_root"]
    _code, status_out, _stderr = await _run_git(root, "status", "--porcelain=v2")
    _code, diff_stat, _stderr = await _run_git(root, "diff", "--stat", "HEAD")
    _code, staged_stat, _stderr = await _run_git(root, "diff", "--cached", "--stat")
    commits = await _capture_commit_diffs(root, base_head=base_head)

    return {
        "is_linked_worktree": True,
        "worktree_root": root,
        "main_repo_root": context.get("main_repo_root"),
        "branch": context.get("branch"),
        "head_sha": context.get("head_sha"),
        "status_porcelain": status_out,
        "diff_stat": diff_stat,
        "staged_diff_stat": staged_stat,
        "commits": commits,
    }


async def _capture_commit_diffs(worktree_root: str, *, base_head: str | None) -> list[dict[str, Any]]:
    rev_range = f"{base_head}..HEAD" if base_head else "main..HEAD"
    code, log_out, _stderr = await _run_git(
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
    code, output, _stderr = await _run_git(worktree_root, *diff_args)
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


async def handle_git_worktree_request(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    if action == "detect":
        path = payload.get("path")
        if not isinstance(path, str) or not path.strip():
            return {"ok": False, "error": "path is required"}
        context = await detect_git_context(path)
        return {"ok": True, "context": context}

    if action == "snapshot":
        worktree_root = payload.get("worktree_root")
        if not isinstance(worktree_root, str) or not worktree_root.strip():
            return {"ok": False, "error": "worktree_root is required"}
        base_head = payload.get("base_head") if isinstance(payload.get("base_head"), str) else None
        snapshot = await capture_worktree_snapshot(worktree_root, base_head=base_head)
        return {"ok": True, "snapshot": snapshot}

    if action == "list_worktrees":
        main_repo_root = payload.get("main_repo_root")
        if not isinstance(main_repo_root, str) or not main_repo_root.strip():
            return {"ok": False, "error": "main_repo_root is required"}
        worktrees = await list_worktrees(main_repo_root)
        return {"ok": True, "worktrees": worktrees}

    return {"ok": False, "error": f"unknown action: {action}"}
