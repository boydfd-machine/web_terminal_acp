import json
import re
from pathlib import Path

import pytest

from app.platform.plugins.artifact_plugins.builtin_component_sources import (
    builtin_artifact_plugin_components,
)
from app.platform.plugins.artifact_plugins.builtin_preview_fixtures import (
    builtin_preview_content_json_by_locale,
)
from app.platform.plugins.artifact_plugins.management import (
    builtin_artifact_plugins,
    builtin_terminal_artifact_plugins,
)
from app.platform.plugins.artifact_plugins.preview import render_component_preview_html


ACAS_PROJECT_CURRENT_KINDS = {
    "user_journey": "UserJourneyCurrent",
    "flow_model": "FlowModelCurrent",
    "low_fi_prototype": "LowFiPrototypeCurrent",
    "capability_map": "CapabilityMapCurrent",
    "glossary": "GlossaryCurrent",
    "domain_design": "DomainDesignCurrent",
    "ui_spec": "UISpecCurrent",
}

ACAS_RENDERER_TITLES = {
    "user_journey": "ACAS User Journey Renderer",
    "flow_model": "ACAS Flow Model Renderer",
    "low_fi_prototype": "ACAS Low-fi Prototype Renderer",
    "capability_map": "ACAS Capability Map",
    "glossary": "ACAS Glossary Renderer",
    "domain_design": "ACAS Domain Design Renderer",
    "ui_spec": "ACAS UI Spec Renderer",
}


def test_builtin_template_preview_data_is_realistic_and_renderer_ready() -> None:
    seen: set[str] = set()
    for plugin in builtin_terminal_artifact_plugins():
        components = builtin_artifact_plugin_components(plugin)
        assert components is not None, f"{plugin.artifact_kind} must be editable as a template preview"
        seen.add(plugin.artifact_kind)
        previews_by_locale = builtin_preview_content_json_by_locale(plugin, components.json_schema)
        rendered_by_locale: dict[str, str] = {}

        assert set(previews_by_locale) == {"en", "zh"}
        assert previews_by_locale["en"] == components.preview_content_json
        assert previews_by_locale["zh"] != previews_by_locale["en"]
        assert _contains_cjk(previews_by_locale["zh"])
        assert components.preview_content_json.get("title") not in {
            "Preview",
            "Example",
            plugin.default_title,
        }

        for locale, locale_preview in previews_by_locale.items():
            html = render_component_preview_html(
                python_source=components.python_source,
                prompt_template=components.prompt_template,
                html_template=components.html_template,
                json_schema=components.json_schema,
                preview_content_json=locale_preview,
            )
            assert html.startswith("<!doctype html>")
            assert "| tojson_pretty" not in components.html_template
            assert "<pre>{</pre>" not in html
            rendered_by_locale[locale] = html

        _assert_kind_preview(plugin.artifact_kind, components.preview_content_json, rendered_by_locale["en"])

    assert seen == {"agent_trace_graph"}


def test_builtin_project_acas_current_artifacts_validate_and_render() -> None:
    seen: set[str] = set()

    for plugin in builtin_artifact_plugins("project"):
        artifact_kind = plugin.artifact_kind
        seen.add(artifact_kind)
        components = builtin_artifact_plugin_components(plugin)

        assert components is not None
        if artifact_kind == "user_journey":
            assert _acas_user_journey_layer_kinds(components.json_schema) == {
                "UserJourneyRaw",
                "UserJourneyCompetitorResearch",
                "UserJourneyExploration",
                "Decision",
                "Principle",
                "UserJourneyCurrent",
            }
            assert "Raw captures original inputs" in components.prompt_template
            assert "Do not skip directly to Current" in components.prompt_template
        else:
            assert components.json_schema["properties"]["kind"]["const"] == ACAS_PROJECT_CURRENT_KINDS[artifact_kind]
        assert components.preview_content_json["kind"] == ACAS_PROJECT_CURRENT_KINDS[artifact_kind]
        assert "https://acas.local/artifact-definitions/_shared/review-decision/schemas/decision-trace.schema.json#/$defs/decisionTrace" in str(components.json_schema)
        assert f"Use ${artifact_kind.replace('_', '-')}-methodology" in components.prompt_template
        if artifact_kind == "user_journey":
            assert components.preview_content_json["journey"]["scenario"] == (
                "Manage one agent-driven project todo across phased work, artifacts, review, and merge"
            )
            assert components.preview_content_json["decisionTrace"]["selectedOptionId"] == (
                "single_todo_phase_work_item_journey"
            )
            assert {
                branch["branchId"]
                for branch in components.preview_content_json["journey"]["branches"]
            } >= {
                "phase_promoted_to_child",
                "board_polling_lock_contention",
                "terminal_latency_pressure",
            }
            assert "artifact_lock_wait_count" in str(components.preview_content_json)
            assert "ProjectTodoWorkItem" in str(components.preview_content_json)
            assert "support issue" not in str(components.preview_content_json).lower()

        rendered = plugin.render(components.preview_content_json)
        html = rendered.display_html

        assert rendered.metadata_json["artifact_kind"] == artifact_kind
        assert rendered.metadata_json["renderer"].startswith("acas-")
        assert html.startswith("<!doctype html>")
        assert ACAS_RENDERER_TITLES[artifact_kind] in html
        assert "window.__ACAS_RENDER_RESOURCE__" in html
        assert "acas-render-resource" in html
        assert components.preview_content_json["kind"] in html

    assert seen == set()


def test_user_journey_project_artifact_accepts_all_acas_layers() -> None:
    pytest.skip("Project ACAS artifacts are no longer system built-ins.")
    layer_examples = [
        {
            "kind": "UserJourneyRaw",
            "layer": "Raw",
            "rawInputs": [
                {
                    "inputId": "input_001",
                    "sourceType": "user_text",
                    "content": "User needs support status visibility.",
                }
            ],
            "researchGate": {
                "competitorResearchNeeded": True,
                "urgency": "recommended",
                "reason": "Early product journey design benefits from market patterns.",
            },
        },
        {
            "kind": "UserJourneyCompetitorResearch",
            "layer": "Competitor Research",
            "researchPerformed": True,
            "relevantPatterns": [
                {
                    "pattern": "status timeline",
                    "implicationForJourney": "Make waiting progress visible.",
                }
            ],
        },
        {
            "kind": "UserJourneyExploration",
            "layer": "Exploration",
            "inferredBoundary": {"confidence": "medium"},
            "journeyOptions": [
                {
                    "optionId": "minimal_status",
                    "title": "Minimal status",
                    "asIs": {"phases": [{"phaseId": "ask", "userGoal": "Ask for status"}]},
                    "toBe": {"phases": [{"phaseId": "track", "userGoal": "Track status"}]},
                },
                {
                    "optionId": "guided_status",
                    "title": "Guided status",
                    "asIs": {"phases": [{"phaseId": "ask", "userGoal": "Ask for status"}]},
                    "toBe": {"phases": [{"phaseId": "preview", "userGoal": "Know next action"}]},
                },
            ],
            "clarificationQuestions": [
                {
                    "questionId": "q_actor",
                    "question": "Who is the actor?",
                    "whyItMatters": "Changes the journey boundary.",
                    "affects": ["boundary"],
                    "answerType": "single_choice",
                    "recommendedOptionId": "customer",
                    "options": [{"optionId": "customer", "label": "A"}],
                }
            ],
        },
        {
            "kind": "UserJourneyDecision",
            "layer": "Decision",
            "decisionId": "decision_001",
            "artifactId": "user_journey_001",
            "fromLayer": "Exploration",
            "toLayer": "Current",
            "status": "ready_to_apply",
            "optionDecision": {"selectedOptionId": "guided_status"},
            "questions": [],
        },
        {
            "kind": "UserJourneyPrinciple",
            "layer": "Principle",
            "principleSetId": "principles_001",
            "artifactId": "user_journey_001",
            "status": "draft_for_review",
            "scope": {"artifact": "user_journey"},
            "sourceRefs": ["current:user_journey_001"],
            "principles": [
                {
                    "principleId": "make_waiting_visible",
                    "title": "Make waiting visible",
                    "statement": "Every waiting state explains next action.",
                    "why": "Silent waiting causes duplicate follow-up.",
                    "confirmation": {"mode": "agent_decided", "result": "included"},
                    "appliesTo": {"scopes": ["track"]},
                }
            ],
        },
    ]

    for example in layer_examples:
        parsed = plugin.parse_output(f"prefix {json.dumps(example)} suffix")
        assert parsed["kind"] == example["kind"]
        rendered = plugin.render(example)
        assert rendered.metadata_json["artifact_kind"] == "user_journey"
        assert example["kind"] in rendered.display_html


def test_acas_project_artifact_methodology_skills_are_migrated_for_all_agent_clients() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    agent_skill_roots = [
        repo_root / ".codex" / "skills",
        repo_root / ".claude" / "skills",
        repo_root / ".cursor" / "skills",
    ]
    missing: list[str] = []

    for plugin in builtin_artifact_plugins("project"):
        components = builtin_artifact_plugin_components(plugin)
        assert components is not None
        skill_refs = set(re.findall(r"\$([A-Za-z0-9_-]+)", components.prompt_template))
        methodology_refs = {ref for ref in skill_refs if ref.endswith("-methodology")}
        assert methodology_refs, f"{plugin.artifact_kind} prompt must name its ACAS methodology skill"
        for skill_ref in methodology_refs:
            for skill_root in agent_skill_roots:
                skill_md = skill_root / skill_ref / "SKILL.md"
                if not skill_md.is_file():
                    missing.append(str(skill_md.relative_to(repo_root)))

    assert missing == []


def _acas_user_journey_layer_kinds(json_schema: dict) -> set[str]:
    kinds: set[str] = set()
    for layer_schema in json_schema["oneOf"]:
        kind = layer_schema["properties"]["kind"]
        if "const" in kind:
            kinds.add(kind["const"])
        else:
            kinds.add(kind["pattern"].replace("$", ""))
    return kinds


def _assert_kind_preview(artifact_kind: str, preview: dict, html: str) -> None:
    if artifact_kind == "agent_trace_graph":
        assert len(preview["goals"]) >= 3
        assert len(preview["nodes"]) >= 6
        assert len(preview["edges"]) >= 5
        assert {node["status"] for node in preview["nodes"]} >= {"success", "warning", "error"}
        assert "<svg" in html
        assert 'data-from="n3" data-to="n5"' in html
        assert 'class="edge deadend tree"' in html
        assert "<pre>" not in html
        return

    if artifact_kind == "agent_pitfalls":
        assert len(preview["pitfalls"]) >= 4
        assert {item["solution_type"] for item in preview["pitfalls"]} == {
            "install_software",
            "update_memory",
            "add_skill",
            "add_tool",
        }
        assert 'class="lanes"' in html
        assert "Install Software" in html
        assert "<pre>" not in html
        return

    if artifact_kind == "page_review_cards":
        assert len(preview["cards"]) >= 4
        assert {card["type"] for card in preview["cards"]} >= {
            "interaction",
            "accessibility",
            "performance",
        }
        assert 'class="board"' in html
        assert "Acceptance criteria" in html
        assert "<pre>" not in html
        return

    if artifact_kind == "deep_research_report":
        assert len(preview["highlights"]) >= 2
        assert len(preview["sections"]) >= 2
        assert "| Artifact | Preferred display | Reason |" in preview["source_markdown"]
        assert "research-highlight-grid" in html
        assert "Research Analysis" in html
        assert "Comparison Matrix" in html
        assert "Recommendations" in html
        assert "Raw Source Markdown" in html
        assert "<table>" in html
        assert "https://example.test/artifact-preview-guidance" in html
        return

    if artifact_kind == "requirement_review_report":
        assert preview["executive_summary"]
        assert len(preview["project_todo_cards"]) >= 2
        assert "Requirement review for artifact todo creation" in html
        assert "Candidate Todo Cards" in html
        assert "<pre>" not in html
        return

    assert len(preview["sections"]) >= 3
    assert all(len(section["items"]) >= 2 for section in preview["sections"])
    assert len(preview.get("decisions", [])) >= 2
    assert "<table>" in html
    assert 'aria-label="Decisions"' in html
    assert "<pre>" not in html


def _contains_cjk(value: object) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value))
