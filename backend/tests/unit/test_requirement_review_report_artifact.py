import pytest

from app.platform.plugins.artifact_plugins.registry import get_terminal_artifact_plugin_registry
from app.platform.plugins.artifact_plugins.requirement_review_report import (
    RequirementReviewReportArtifactPlugin,
    normalize_requirement_review_report,
)


def test_requirement_review_report_normalizes_rubric_and_candidate_cards() -> None:
    content = normalize_requirement_review_report(
        {
            "artifact_kind": "requirement_review_report",
            "title": "Requirement review",
            "source_requirement": {"title": "Fix broken login", "todo_type_id": "debug"},
            "detected_type": "bug",
            "verdict": "needs_split",
            "confidence": "high",
            "executive_summary": "The bug is valid but needs repro details.",
            "rubric": {
                "type": "bug",
                "criteria": [
                    {
                        "label": "Reproduction is clear",
                        "result": "concern",
                        "evidence": ["Login failure is reported."],
                        "assumptions": ["The issue affects all users."],
                        "suggestions": ["Add expected vs actual behavior."],
                    }
                ],
            },
            "project_todo_cards": [
                {
                    "id": "REQ-001",
                    "title": "Reproduce login failure",
                    "type": "bug",
                    "description": "Capture steps and affected environment.",
                    "acceptance_criteria": ["A failing regression test exists."],
                }
            ],
        }
    )

    assert content["detected_type"] == "bug"
    assert content["rubric"]["criteria"][0]["result"] == "concern"
    assert content["project_todo_cards"][0]["todo_type_id"] == "default"
    assert content["project_todo_cards"][0]["artifact_kinds"] == []
    assert "A failing regression test exists." in content["project_todo_cards"][0]["description"]
    assert "Recommended todo type" not in content["project_todo_cards"][0]["description"]


def test_requirement_review_report_strips_candidate_card_type_metadata_from_description() -> None:
    content = normalize_requirement_review_report(
        {
            "project_todo_cards": [
                {
                    "id": "REQ-001",
                    "title": "Confirm CMS scope",
                    "todo_type_id": "product-design",
                    "description": (
                        "Clarify CMS content types and roles.\n\n"
                        "Recommended todo type: product-design\n"
                        "Recommended todo type: product-design"
                    ),
                    "acceptance_criteria": ["CMS MVP scope is documented."],
                }
            ],
        }
    )

    [card] = content["project_todo_cards"]
    assert card["todo_type_id"] == "default"
    assert "Clarify CMS content types and roles." in card["description"]
    assert "CMS MVP scope is documented." in card["description"]
    assert "Recommended todo type" not in card["description"]


def test_requirement_review_report_normalizes_generated_card_type_and_artifact_aliases() -> None:
    content = normalize_requirement_review_report(
        {
            "executive_summary": "The requirement should become an actionable implementation card.",
            "project_todo_cards": [
                {
                    "id": "REQ-001",
                    "title": "Build the CMS publishing workflow",
                    "todo_type_id": "cms-feature",
                    "artifact_kinds": [
                        "requirement_spec",
                        "ui_review",
                        "test_report",
                        "project:user_journey",
                    ],
                }
            ],
        }
    )

    [card] = content["project_todo_cards"]
    assert card["todo_type_id"] == "default"
    assert card["artifact_kinds"] == []


def test_requirement_review_report_renders_project_todo_bridge() -> None:
    plugin = RequirementReviewReportArtifactPlugin()

    rendered = plugin.render(
        {
            "executive_summary": "Ready after one clarification.",
            "optimized_requirement": {
                "title": "Add empty-state action",
                "description": "Expose a clear action when the list is empty.",
                "todo_type_id": "ui-change",
                "acceptance_criteria": ["The empty state has one primary action."],
            },
        }
    )

    assert rendered.metadata_json == {
        "renderer": "requirement-review-report",
        "artifact_kind": "requirement_review_report",
    }
    assert rendered.content_json["project_todo_cards"][0]["todo_type_id"] == "default"
    assert "web-terminal.project-todo.create" in rendered.display_html
    assert "Add to board" in rendered.display_html
    assert "project-todo-cards" in rendered.display_html


def test_requirement_review_report_is_registered_as_template_builtin() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: requirement_review_report"):
        get_terminal_artifact_plugin_registry().by_kind("requirement_review_report")
