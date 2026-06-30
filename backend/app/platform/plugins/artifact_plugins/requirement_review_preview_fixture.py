from __future__ import annotations

from typing import Any


def requirement_review_preview(locale: str) -> dict[str, Any]:
    preview = _requirement_review_preview()
    if locale != "zh":
        return preview
    preview.update(
        {
            "locale": "zh",
            "title": "需求优化 artifact 预览",
            "executive_summary": "方向合理，但首版应先输出结构化建议和候选卡片，不自动改原卡，也不自动阻止执行。",
            "recommended_next_step": "由用户确认后，再把需要的候选卡添加到看板。",
        }
    )
    return preview


def _requirement_review_preview() -> dict[str, Any]:
    return {
        "artifact_kind": "requirement_review_report",
        "locale": "en",
        "title": "Requirement review for artifact todo creation",
        "source_requirement": {
            "title": "Create child cards from requirement artifact",
            "description": "Let artifact HTML present optimized requirements and add selected cards to the board.",
            "todo_type_id": "large-feature",
        },
        "detected_type": "large-feature",
        "verdict": "needs_split",
        "confidence": "high",
        "executive_summary": "The direction is reasonable, but the bridge contract and artifact schema should ship before any automatic todo mutation.",
        "rubric": {
            "type": "large-feature",
            "criteria": [
                _criterion("RR-01", "User value is explicit", "pass", "Users can choose which optimized cards to add.", "Assumes the source artifact is linked to the project.", "Keep card creation user-confirmed."),
                _criterion("RR-02", "Scope can be staged", "concern", "Schema, renderer, and apply actions are separable.", "Parent todo linking may need a later bridge field.", "Ship report plus card list first."),
            ],
        },
        "evidence": [{"label": "Architecture", "detail": "Todo types already drive dispatch templates and artifact kinds."}],
        "assumptions": ["The review artifact is advice only until the user clicks Add to board."],
        "clarifying_questions": [{"question": "Should child cards inherit a parent todo id?", "why": "The current iframe card bridge can link the source artifact but not a parent card."}],
        "optimized_requirement": {
            "title": "Add requirement review report artifact",
            "description": "Create a structured artifact that reviews requirement quality and proposes user-confirmed follow-up cards.",
            "todo_type_id": "large-feature",
            "acceptance_criteria": ["The report renders rubric conclusions.", "Candidate cards can be added through the artifact bridge."],
            "non_goals": ["Do not auto-edit the original todo.", "Do not block dispatch automatically."],
        },
        "recommendations": ["Use requirement-review as a dedicated todo type.", "Keep automatic application out of the first release."],
        "recommended_next_step": "Review the generated cards and add only the ones the user wants.",
        "project_todo_cards": [
            _card("REQ-001", "Add requirement review artifact schema", "large-feature", "Define fields for verdict, evidence, assumptions, questions, optimized requirement, and candidate todos."),
            _card("REQ-002", "Add one-click cards to requirement report", "ui-change", "Render candidate cards with Add to board buttons that use the artifact iframe bridge."),
        ],
    }


def _criterion(item_id: str, label: str, result: str, evidence: str, assumption: str, suggestion: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "result": result,
        "evidence": [evidence],
        "assumptions": [assumption],
        "suggestions": [suggestion],
    }


def _card(card_id: str, title: str, todo_type_id: str, description: str) -> dict[str, Any]:
    return {
        "id": card_id,
        "title": title,
        "description": description,
        "status": "TODO",
        "todo_type_id": todo_type_id,
        "artifact_kinds": [],
        "review_strategy": "LOCAL_CARD",
    }
