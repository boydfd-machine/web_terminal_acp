from __future__ import annotations

import re
import shlex
from typing import Any

_GIT_WORKTREE_ADD_RE = re.compile(r"\bgit\s+worktree\s+add\b", re.IGNORECASE)


def parse_git_worktree_add_path(command: str, cwd: str | None) -> str | None:
    if not _GIT_WORKTREE_ADD_RE.search(command):
        return None

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    path_tokens: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        lower = token.lower()
        if lower in {"-f", "--force", "-b", "-B", "--orphan", "--detach", "-q", "--quiet"}:
            if lower in {"-b", "-B", "--orphan"}:
                skip_next = True
            continue
        if lower in {"add", "git", "worktree"}:
            continue
        if token.startswith("-"):
            continue
        path_tokens.append(token)
        break

    if not path_tokens:
        return None

    raw_path = path_tokens[0]
    if raw_path.startswith("/"):
        return raw_path
    if cwd:
        return f"{cwd.rstrip('/')}/{raw_path}"
    return raw_path


def compute_session_diff(
    start_snapshot: dict[str, Any] | None,
    end_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not start_snapshot or not end_snapshot:
        return {"has_changes": False}

    start_head = start_snapshot.get("head_sha")
    end_head = end_snapshot.get("head_sha")
    head_moved = bool(start_head and end_head and start_head != end_head)

    start_status = start_snapshot.get("status_porcelain") or ""
    end_status = end_snapshot.get("status_porcelain") or ""
    dirty_at_end = bool(end_status.strip())
    status_changed = start_status != end_status
    commits = _snapshot_commits(end_snapshot)

    has_changes = head_moved or dirty_at_end or status_changed
    return {
        "has_changes": has_changes,
        "head_moved": head_moved,
        "start_head": start_head,
        "end_head": end_head,
        "uncommitted_at_end": dirty_at_end,
        "start_status_porcelain": start_status,
        "end_status_porcelain": end_status,
        "end_diff_stat": end_snapshot.get("diff_stat") or "",
        "end_staged_diff_stat": end_snapshot.get("staged_diff_stat") or "",
        "commits": commits,
        "files": _aggregate_commit_files(commits),
    }


def pending_commit_from_diff(session_diff: dict[str, Any]) -> bool:
    return bool(session_diff.get("has_changes") and session_diff.get("uncommitted_at_end"))


def pending_commit_from_live_snapshot(snapshot: dict[str, Any]) -> bool:
    if not snapshot.get("is_linked_worktree"):
        return False
    status = snapshot.get("status_porcelain") or ""
    return bool(status.strip())


def _snapshot_commits(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    commits = snapshot.get("commits")
    if not isinstance(commits, list):
        return []
    return [commit for commit in commits if isinstance(commit, dict)]


def _aggregate_commit_files(commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    files_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}
    for commit in commits:
        commit_sha = commit.get("sha")
        files = commit.get("files")
        if not isinstance(commit_sha, str) or not isinstance(files, list):
            continue
        for file_change in files:
            if not isinstance(file_change, dict):
                continue
            path = file_change.get("path")
            old_path = file_change.get("old_path")
            if not isinstance(path, str) or not path:
                continue
            normalized_old_path = old_path if isinstance(old_path, str) and old_path else None
            key = (path, normalized_old_path)
            aggregate = files_by_key.setdefault(
                key,
                {
                    "path": path,
                    "old_path": normalized_old_path,
                    "status": file_change.get("status") or "modified",
                    "additions": 0,
                    "deletions": 0,
                    "commits": [],
                },
            )
            aggregate["additions"] += _safe_int(file_change.get("additions"))
            aggregate["deletions"] += _safe_int(file_change.get("deletions"))
            aggregate["status"] = file_change.get("status") or aggregate["status"]
            aggregate["commits"].append(commit_sha)
    return sorted(files_by_key.values(), key=lambda item: str(item.get("path") or ""))


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
