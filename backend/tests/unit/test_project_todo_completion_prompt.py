import json

from app.contexts.workspace.application.project_todo_completion_prompt import (
    build_verification_prompt,
    parse_verification_verdict,
    verification_json_complete,
)
from app.models import ProjectTodo


def test_parse_verification_verdict_extracts_json_from_text() -> None:
    text = "Some preamble\n" + json.dumps({
        "verdict": "complete",
        "evidence": "all good",
        "open_processes": ["dev"],
    }) + "\ntail"
    verdict = parse_verification_verdict(text, fallback_processes=[])
    assert verdict.verdict == "complete"
    assert verdict.evidence == "all good"
    assert verdict.open_processes == ["dev"]


def test_parse_verification_verdict_handles_invalid_json() -> None:
    verdict = parse_verification_verdict("not json", fallback_processes=["a"])
    assert verdict.verdict == "error"
    assert verdict.open_processes == ["a"]


def test_verification_json_complete_recognizes_valid_payload() -> None:
    assert verification_json_complete(json.dumps({"verdict": "complete"})) is True
    assert verification_json_complete("garbage") is False
    assert verification_json_complete(json.dumps({"foo": "bar"})) is False


def test_build_verification_prompt_marks_background_wait_context() -> None:
    todo = ProjectTodo(title="Delayed work", description="Run a delayed background task.")

    prompt = build_verification_prompt(
        todo,
        attempt=1,
        active_processes=[],
        waited_for_background_work=True,
    )

    assert "previously waited for a background task" in prompt
    assert "main agent clearly reported" in prompt
    assert "no active non-shell processes were detected" in prompt
