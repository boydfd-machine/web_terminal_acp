from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models import ProjectTodo


@dataclass
class VerificationVerdict:
    verdict: str  # "complete" | "incomplete" | "error"
    evidence: str
    open_processes: list[str]


def build_verification_prompt(
    todo: ProjectTodo,
    *,
    attempt: int,
    active_processes: list[str],
    waited_for_background_work: bool = False,
    output_path: str | None = None,
) -> str:
    acceptance = ""
    criteria_json = getattr(todo, "acceptance_criteria_json", None)
    if criteria_json:
        try:
            acceptance = json.dumps(criteria_json, ensure_ascii=False, indent=2)
        except Exception:
            acceptance = str(criteria_json)
    open_processes_text = "\n".join(f"- {p}" for p in active_processes[:20]) or "(none detected)"
    description = todo.description or "(no description provided)"
    process_context = (
        "The previous agent finished its turn but some processes are still running:\n"
        if active_processes
        else "The previous agent finished its turn and no active non-shell processes were detected:\n"
    )
    background_context = (
        "This todo previously waited for a background task. Treat the todo as incomplete unless "
        "the main agent clearly reported the delayed/background work's final completion after it finished.\n\n"
        if waited_for_background_work
        else ""
    )
    target_output_path = output_path or f"/tmp/web-terminal-todo-verification-{todo.id}-{attempt}.json"
    return (
        "You are verifying whether the assigned task is genuinely complete.\n\n"
        f"Task: {todo.title}\n"
        f"Description: {description}\n"
        f"Acceptance criteria:\n{acceptance or '(not provided)'}\n\n"
        f"{background_context}"
        f"{process_context}"
        f"{open_processes_text}\n\n"
        "Inspect the workspace, git status, and the running processes. Decide if the "
        "task is fully done. The running processes should only be long-lived services "
        "that the task expects to keep running (e.g. dev servers), not unfinished work.\n\n"
        f"Write ONLY to {target_output_path} a JSON object "
        "exactly matching:\n"
        '{"verdict": "complete" | "incomplete",\n'
        ' "evidence": "<one short sentence>",\n'
        ' "open_processes": ["..."]}\n\n'
        "Do not modify any source files. Do not write anywhere else."
    )


def verification_json_complete(text: str) -> bool:
    try:
        data = json.loads(text)
    except Exception:
        return False
    return isinstance(data, dict) and "verdict" in data


def parse_verification_verdict(text: str, *, fallback_processes: list[str]) -> VerificationVerdict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
    except Exception:
        return VerificationVerdict("error", "could not parse verdict JSON", fallback_processes)
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in {"complete", "incomplete"}:
        return VerificationVerdict("error", f"unknown verdict value: {verdict!r}", fallback_processes)
    evidence = str(data.get("evidence", "")).strip()
    open_processes_raw = data.get("open_processes", [])
    open_processes = (
        [str(item) for item in open_processes_raw]
        if isinstance(open_processes_raw, list)
        else fallback_processes
    )
    return VerificationVerdict(verdict, evidence, open_processes)
