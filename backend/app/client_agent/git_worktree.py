from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any

from app.client_agent.git_worktree_diffs import capture_commit_diffs

_GIT_TIMEOUT_SECONDS = 2.0
_MAIN_BRANCH_CANDIDATES = ("main", "master")


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
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(ProcessLookupError):
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


async def capture_worktree_snapshot(
    worktree_root: str,
    *,
    base_head: str | None = None,
    main_repo_root: str | None = None,
    known_head_sha: str | None = None,
    known_branch: str | None = None,
) -> dict[str, Any]:
    context = await detect_git_context(worktree_root)
    if not context.get("is_linked_worktree"):
        return await _capture_removed_worktree_snapshot(
            worktree_root,
            base_head=base_head,
            main_repo_root=main_repo_root,
            known_head_sha=known_head_sha,
            known_branch=known_branch,
        )

    root = context["worktree_root"]
    _code, status_out, _stderr = await _run_git(root, "status", "--porcelain=v2")
    _code, diff_stat, _stderr = await _run_git(root, "diff", "--stat", "HEAD")
    _code, staged_stat, _stderr = await _run_git(root, "diff", "--cached", "--stat")
    commits = await capture_commit_diffs(_run_git, root, base_head=base_head)
    merge_state = await _capture_merge_state(
        main_repo_root=context.get("main_repo_root"),
        worktree_head=context.get("head_sha"),
        worktree_status=status_out,
    )

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
        **merge_state,
    }


async def _capture_removed_worktree_snapshot(
    worktree_root: str,
    *,
    base_head: str | None,
    main_repo_root: str | None,
    known_head_sha: str | None,
    known_branch: str | None,
) -> dict[str, Any]:
    if not main_repo_root or not known_head_sha:
        return {"is_linked_worktree": False, "worktree_root": worktree_root}

    root = _normalize_path(worktree_root)
    main_root = _normalize_path(main_repo_root)
    commits = await capture_commit_diffs(
        _run_git,
        main_root,
        base_head=base_head,
        head=known_head_sha,
    )
    merge_state = await _capture_merge_state(
        main_repo_root=main_root,
        worktree_head=known_head_sha,
        worktree_status="",
    )
    return {
        "is_linked_worktree": False,
        "worktree_root": root,
        "main_repo_root": main_root,
        "branch": known_branch,
        "head_sha": known_head_sha,
        "status_porcelain": "",
        "diff_stat": "",
        "staged_diff_stat": "",
        "commits": commits,
        **merge_state,
    }


async def _capture_merge_state(
    *,
    main_repo_root: object,
    worktree_head: object,
    worktree_status: str,
) -> dict[str, Any]:
    if not isinstance(main_repo_root, str) or not main_repo_root.strip() or not os.path.isdir(main_repo_root):
        return _merge_state("unknown", "main_repo_unavailable")
    if not isinstance(worktree_head, str) or not worktree_head.strip():
        return _merge_state("unknown", "worktree_head_unavailable")

    main_branch, main_head = await _resolve_main_branch(main_repo_root)
    merge_head = await _main_merge_head(main_repo_root)
    _code, main_status, _stderr = await _run_git(main_repo_root, "status", "--porcelain=v2")
    unmerged_files = _unmerged_files_from_porcelain(main_status)
    merge_matches_worktree = merge_head == worktree_head if merge_head and worktree_head else None

    if merge_matches_worktree and unmerged_files:
        return _merge_state(
            "conflict",
            "main_merge_conflict",
            main_branch=main_branch,
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=True,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )
    if merge_matches_worktree:
        return _merge_state(
            "unmerged",
            "main_merge_in_progress",
            main_branch=main_branch,
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=True,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )
    if worktree_status.strip():
        return _merge_state(
            "unmerged",
            "worktree_has_uncommitted_changes",
            main_branch=main_branch,
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=merge_head is not None,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )
    if main_branch is None:
        return _merge_state(
            "unknown",
            "main_branch_unavailable",
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=merge_head is not None,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )

    code, _stdout, _stderr = await _run_git(
        main_repo_root,
        "merge-base",
        "--is-ancestor",
        worktree_head,
        main_branch,
    )
    if code == 0:
        return _merge_state(
            "merged",
            "head_is_ancestor_of_main",
            merged_to_main=True,
            main_branch=main_branch,
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=merge_head is not None,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )
    if code == 1:
        return _merge_state(
            "unmerged",
            "head_not_merged_to_main",
            merged_to_main=False,
            main_branch=main_branch,
            main_head_sha=main_head,
            main_merge_head_sha=merge_head,
            main_merge_in_progress=merge_head is not None,
            main_merge_matches_worktree=merge_matches_worktree,
            unmerged_files=unmerged_files,
        )
    return _merge_state(
        "unknown",
        "merge_base_unavailable",
        main_branch=main_branch,
        main_head_sha=main_head,
        main_merge_head_sha=merge_head,
        main_merge_in_progress=merge_head is not None,
        main_merge_matches_worktree=merge_matches_worktree,
        unmerged_files=unmerged_files,
    )


async def _resolve_main_branch(main_repo_root: str) -> tuple[str | None, str | None]:
    for branch in _MAIN_BRANCH_CANDIDATES:
        code, head, _stderr = await _run_git(main_repo_root, "rev-parse", "--verify", branch)
        if code == 0 and head:
            return branch, head
    code, head, _stderr = await _run_git(main_repo_root, "rev-parse", "HEAD")
    return None, head if code == 0 and head else None


async def _main_merge_head(main_repo_root: str) -> str | None:
    git_dir_code, git_dir, _stderr = await _run_git(main_repo_root, "rev-parse", "--git-dir")
    if git_dir_code != 0 or not git_dir:
        return None
    merge_head_path = Path(git_dir)
    if not merge_head_path.is_absolute():
        merge_head_path = Path(main_repo_root) / merge_head_path
    merge_head_path = merge_head_path / "MERGE_HEAD"
    try:
        merge_head = merge_head_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (IndexError, OSError):
        return None
    return merge_head or None


def _merge_state(
    status: str,
    reason: str,
    *,
    merged_to_main: bool | None = None,
    main_branch: str | None = None,
    main_head_sha: str | None = None,
    main_merge_head_sha: str | None = None,
    main_merge_in_progress: bool = False,
    main_merge_matches_worktree: bool | None = None,
    unmerged_files: list[str] | None = None,
) -> dict[str, Any]:
    if merged_to_main is None and status in {"merged", "unmerged", "conflict"}:
        merged_to_main = status == "merged"
    return {
        "merge_status": status,
        "merge_status_reason": reason,
        "merged_to_main": merged_to_main,
        "main_branch": main_branch,
        "main_head_sha": main_head_sha,
        "main_merge_head_sha": main_merge_head_sha,
        "main_merge_in_progress": main_merge_in_progress,
        "main_merge_matches_worktree": main_merge_matches_worktree,
        "unmerged_files": unmerged_files or [],
    }


def _unmerged_files_from_porcelain(status: str) -> list[str]:
    files: list[str] = []
    for raw_line in status.splitlines():
        line = raw_line.strip()
        if not line.startswith("u "):
            continue
        parts = line.split(" ")
        if len(parts) >= 11:
            files.append(parts[-1])
    return files


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
        main_repo_root = (
            payload.get("main_repo_root") if isinstance(payload.get("main_repo_root"), str) else None
        )
        known_head_sha = (
            payload.get("known_head_sha") if isinstance(payload.get("known_head_sha"), str) else None
        )
        known_branch = payload.get("known_branch") if isinstance(payload.get("known_branch"), str) else None
        snapshot = await capture_worktree_snapshot(
            worktree_root,
            base_head=base_head,
            main_repo_root=main_repo_root,
            known_head_sha=known_head_sha,
            known_branch=known_branch,
        )
        return {"ok": True, "snapshot": snapshot}

    if action == "list_worktrees":
        main_repo_root = payload.get("main_repo_root")
        if not isinstance(main_repo_root, str) or not main_repo_root.strip():
            return {"ok": False, "error": "main_repo_root is required"}
        worktrees = await list_worktrees(main_repo_root)
        return {"ok": True, "worktrees": worktrees}

    return {"ok": False, "error": f"unknown action: {action}"}
