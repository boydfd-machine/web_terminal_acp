from __future__ import annotations

import re
import shlex
from typing import Any

_GIT_WORKTREE_ADD_RE = re.compile(r"\bgit\s+worktree\s+add\b", re.IGNORECASE)
_GIT_INTEGRATION_RE = re.compile(
    r"\bgit\s+(?:merge|pull|rebase|cherry-pick|revert|am|reset)\b",
    re.IGNORECASE,
)
_MERGE_STATUSES = {"merged", "unmerged", "conflict", "unknown"}
_COMPACT_SNAPSHOT_KEYS = {
    "is_linked_worktree",
    "worktree_root",
    "main_repo_root",
    "branch",
    "head_sha",
    "status_porcelain",
    "diff_stat",
    "staged_diff_stat",
    "merge_status",
    "merge_status_reason",
    "merged_to_main",
    "main_branch",
    "main_head_sha",
    "main_merge_head_sha",
    "main_merge_in_progress",
    "main_merge_matches_worktree",
    "unmerged_files",
}


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


def command_can_change_git_merge_state(command: str) -> bool:
    return bool(_GIT_INTEGRATION_RE.search(command))


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


def compact_git_worktree_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key in _COMPACT_SNAPSHOT_KEYS and value is not None
    }


def pending_commit_from_diff(session_diff: dict[str, Any]) -> bool:
    return bool(session_diff.get("has_changes") and session_diff.get("uncommitted_at_end"))


def pending_commit_from_live_snapshot(snapshot: dict[str, Any]) -> bool:
    if not snapshot.get("is_linked_worktree"):
        return False
    status = snapshot.get("status_porcelain") or ""
    return bool(status.strip())


def git_worktree_merge_state(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return _unknown_merge_state("snapshot_unavailable")

    raw_status = snapshot.get("merge_status")
    status = raw_status if isinstance(raw_status, str) and raw_status in _MERGE_STATUSES else "unknown"
    reason = _string_value(snapshot.get("merge_status_reason")) or "snapshot_unavailable"
    merged_to_main = snapshot.get("merged_to_main")
    if not isinstance(merged_to_main, bool):
        merged_to_main = status == "merged" if status in {"merged", "unmerged", "conflict"} else None

    return {
        "merge_status": status,
        "merge_status_reason": reason,
        "merged_to_main": merged_to_main,
        "main_branch": _string_value(snapshot.get("main_branch")),
        "main_head_sha": _string_value(snapshot.get("main_head_sha")),
        "main_merge_head_sha": _string_value(snapshot.get("main_merge_head_sha")),
        "main_merge_in_progress": bool(snapshot.get("main_merge_in_progress")),
        "main_merge_matches_worktree": _optional_bool(snapshot.get("main_merge_matches_worktree")),
        "unmerged_files": _string_list(snapshot.get("unmerged_files")),
    }


def git_worktree_needs_merge_attention(snapshot: dict[str, Any] | None) -> bool:
    state = git_worktree_merge_state(snapshot)
    return state["merge_status"] in {"unmerged", "conflict"} or state["merged_to_main"] is False


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


def _unknown_merge_state(reason: str) -> dict[str, Any]:
    return {
        "merge_status": "unknown",
        "merge_status_reason": reason,
        "merged_to_main": None,
        "main_branch": None,
        "main_head_sha": None,
        "main_merge_head_sha": None,
        "main_merge_in_progress": False,
        "main_merge_matches_worktree": None,
        "unmerged_files": [],
    }


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]
