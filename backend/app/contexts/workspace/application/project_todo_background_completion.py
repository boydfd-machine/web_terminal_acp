from __future__ import annotations

from datetime import UTC, datetime


BACKGROUND_WORK_RECHECK_ATTEMPT = 1
BACKGROUND_WORK_WAITING_PREFIX = "waiting for active background process before completion review: "
FINAL_COMPLETION_WAITING_PREFIX = "waiting for main agent final completion after background process finished"
BACKGROUND_WORK_COMMAND_NAMES = frozenset(
    {
        "sleep",
        "timeout",
        "bash",
        "zsh",
        "sh",
        "fish",
        "dash",
        "ksh",
        "tcsh",
        "csh",
    }
)


def active_processes_look_like_background_work(active_processes: list[str]) -> bool:
    return any(_active_process_looks_like_background_work(process) for process in active_processes)


def background_work_waiting_error(active_processes: list[str]) -> str:
    return f"{BACKGROUND_WORK_WAITING_PREFIX}{_format_process_list(active_processes)}"[:4000]


def final_completion_waiting_error(completed_at: datetime) -> str:
    return f"{FINAL_COMPLETION_WAITING_PREFIX}: last agent completion at {_ensure_aware(completed_at).isoformat()}"[:4000]


def todo_waited_for_background_work(dispatch_error: str | None) -> bool:
    if not dispatch_error:
        return False
    return dispatch_error.startswith(BACKGROUND_WORK_WAITING_PREFIX) or dispatch_error.startswith(
        FINAL_COMPLETION_WAITING_PREFIX
    )


def ensure_aware(value: datetime) -> datetime:
    return _ensure_aware(value)


def _active_process_looks_like_background_work(process: str) -> bool:
    command = _command_name(process)
    if command in BACKGROUND_WORK_COMMAND_NAMES:
        return True
    lowered = process.lower()
    if "pending subagent" in lowered:
        return True
    return any(token in lowered for token in (" sleep ", "sleep 120", "sleep 60", "settimeout"))


def _command_name(cmdline: str) -> str:
    tokens = cmdline.split()
    if not tokens:
        return ""
    return tokens[0].rsplit("/", 1)[-1].lower()


def _format_process_list(processes: list[str]) -> str:
    return "; ".join(processes[:10]) or "(none)"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
