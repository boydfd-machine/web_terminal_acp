from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .page_review_cards import _append_list, _choice, _clip, _text, _text_list
from .project_todo_card_metadata import (
    DEFAULT_ARTIFACT_KINDS_BY_TODO_TYPE,
    normalize_project_todo_card_artifact_kinds,
    normalize_project_todo_card_type_id,
)
from .types import TerminalArtifactRender

REQUIREMENT_TYPES = {
    "bug",
    "ui",
    "research",
    "quick-fix",
    "small-feature",
    "large-feature",
    "performance-optimization",
    "product-design",
    "review",
    "default",
}
VERDICTS = {"ready", "needs_clarification", "needs_split", "too_broad", "not_recommended", "risky"}
CONFIDENCES = {"high", "medium", "low"}
RUBRIC_RESULTS = {"pass", "concern", "fail", "unknown"}
CARD_DESCRIPTION_TYPE_METADATA_RE = re.compile(
    r"(?:^|\s+)Recommended\s+todo\s+type\s*:\s*[A-Za-z0-9_.:/-]+",
    re.IGNORECASE,
)


class RequirementReviewReportArtifactPlugin:
    artifact_kind = "requirement_review_report"
    label = "Requirement Review Report"
    default_title = "Requirement review report"

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        schema = {
            "artifact_kind": self.artifact_kind,
            "title": "short report title",
            "source_requirement": {
                "title": "todo title",
                "description": "original requirement text",
                "todo_type_id": "current todo type id",
            },
            "detected_type": "bug|ui|research|small-feature|large-feature|performance-optimization|product-design|review|default",
            "verdict": "ready|needs_clarification|needs_split|too_broad|not_recommended|risky",
            "confidence": "high|medium|low",
            "executive_summary": "short product/engineering judgement",
            "rubric": {
                "type": "detected requirement type",
                "criteria": [
                    {
                        "id": "criterion id",
                        "label": "criterion label",
                        "result": "pass|concern|fail|unknown",
                        "evidence": ["concrete evidence"],
                        "assumptions": ["explicit assumption"],
                        "suggestions": ["recommended improvement"],
                    }
                ],
            },
            "evidence": [{"label": "source or observation", "detail": "what supports the conclusion"}],
            "assumptions": ["assumption behind the judgement"],
            "clarifying_questions": [{"question": "question", "why": "why it matters"}],
            "optimized_requirement": {
                "title": "improved todo title",
                "description": "improved todo description",
                "todo_type_id": "recommended built-in todo type",
                "acceptance_criteria": ["testable criterion"],
                "non_goals": ["explicitly excluded scope"],
            },
            "recommendations": ["actionable advice"],
            "recommended_next_step": "what the user should do next",
            "project_todo_cards": [
                {
                    "id": "REQ-001",
                    "title": "split or optimized requirement title",
                    "description": "self-contained card details",
                    "todo_type_id": "quick-fix|ui-change|debug|small-feature|large-feature|solution-research|performance-optimization|review|product-design|user-review|default",
                    "artifact_kinds": ["optional requested artifact kinds"],
                    "status": "TODO|BLOCKED",
                }
            ],
        }
        output_instruction = ""
        if output_path:
            temp_path = f"{output_path}.tmp"
            output_instruction = (
                f" Do not print JSON to chat. Write the final valid JSON to {output_path}."
                f" Prefer writing {temp_path}, validating it, then mv {temp_path} {output_path} atomically."
                " After saving, reply only: artifact JSON saved."
            )
        extra = f" User requirements: {_single_line(user_prompt)}" if user_prompt else ""
        prompt = (
            f"Generate a {self.artifact_kind} artifact for terminal \"{source_title}\". Review the source"
            " project todo requirement, not the implementation. Do not modify the original todo, do not"
            " automatically block dispatch, and do not implement code. Classify the requirement type, then"
            " apply a type-specific rubric: bug/debug requires reproduction, expected vs actual, impact,"
            " and regression signal; UI requires target flow, states, responsive/accessibility evidence,"
            " and design-system fit; research requires decision question, options, constraints, credible"
            " sources, and recommendation criteria; large-feature requires user value, scope boundaries,"
            " dependencies, architecture fit, staged delivery, and acceptance; performance requires metric,"
            " baseline, budget, bottleneck hypothesis, correctness guard, and regression check. Split every"
            " conclusion into evidence, assumptions, and recommendations. Produce project_todo_cards for"
            " optimized or split follow-up requirements; each card must be independently actionable and set"
            " a suitable built-in todo_type_id. Use BLOCKED only when the card cannot start until a named"
            f" clarification is answered.{output_instruction} Output only valid JSON. Do not output Markdown"
            f" fences, HTML, or screenshots. JSON shape: {json.dumps(schema, ensure_ascii=True)}."
            f" Stop after producing the artifact.{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        last_error = ""
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                return normalize_requirement_review_report(candidate)
            except ValueError as exc:
                last_error = str(exc)
        detail = f": {last_error}" if last_error else ""
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output{detail}")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = normalize_requirement_review_report(content_json)
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=_render_html(normalized),
            metadata_json={"renderer": "requirement-review-report", "artifact_kind": self.artifact_kind},
        )


def normalize_requirement_review_report(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("artifact content must be an object")
    artifact_kind = _text(value.get("artifact_kind"))
    if artifact_kind and artifact_kind != RequirementReviewReportArtifactPlugin.artifact_kind:
        raise ValueError("artifact_kind does not match requirement_review_report")
    source = _source_requirement(value.get("source_requirement") or value.get("source_todo"))
    detected_type = _requirement_type(value.get("detected_type") or value.get("requirement_type") or source["todo_type_id"])
    optimized = _optimized_requirement(value.get("optimized_requirement"), detected_type)
    cards = _project_todo_cards(value, detected_type, optimized)
    rubric = _rubric(value.get("rubric") or value.get("criteria"), detected_type)
    summary = _text(value.get("executive_summary") or value.get("summary"))
    if not summary and not rubric["criteria"] and not cards:
        raise ValueError("requirement review must include a summary, rubric criteria, or project todo cards")
    return {
        "artifact_kind": RequirementReviewReportArtifactPlugin.artifact_kind,
        "title": _text(value.get("title")) or RequirementReviewReportArtifactPlugin.default_title,
        "source_requirement": source,
        "detected_type": detected_type,
        "verdict": _choice(_text(value.get("verdict")).lower(), VERDICTS, "needs_clarification"),
        "confidence": _choice(_text(value.get("confidence")).lower(), CONFIDENCES, "medium"),
        "executive_summary": summary or "No summary provided.",
        "rubric": rubric,
        "evidence": _evidence(value.get("evidence")),
        "assumptions": _text_list(value.get("assumptions")),
        "clarifying_questions": _questions(value.get("clarifying_questions") or value.get("questions")),
        "optimized_requirement": optimized,
        "recommendations": _text_list(value.get("recommendations") or value.get("suggestions")),
        "recommended_next_step": _text(value.get("recommended_next_step") or value.get("next_step")),
        "project_todo_cards": cards,
    }


def _source_requirement(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        value = {}
    return {
        "title": _text(value.get("title")),
        "description": _text(value.get("description") or value.get("context")),
        "todo_type_id": _text(value.get("todo_type_id") or value.get("type")) or "default",
        "project_path": _text(value.get("project_path")),
    }


def _optimized_requirement(value: object, fallback_type: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    todo_type_id = _todo_type_id(value.get("todo_type_id") or value.get("type") or fallback_type)
    return {
        "title": _text(value.get("title")),
        "description": _text(value.get("description") or value.get("requirement")),
        "todo_type_id": todo_type_id,
        "acceptance_criteria": _text_list(value.get("acceptance_criteria") or value.get("criteria")),
        "non_goals": _text_list(value.get("non_goals") or value.get("out_of_scope")),
    }


def _rubric(value: object, fallback_type: str) -> dict[str, Any]:
    rubric_type = fallback_type
    criteria_value = value
    if isinstance(value, dict):
        rubric_type = _requirement_type(value.get("type") or value.get("requirement_type") or fallback_type)
        criteria_value = value.get("criteria") or value.get("items") or []
    criteria = [_criterion(item, index) for index, item in enumerate(criteria_value or [], start=1)] if isinstance(criteria_value, list) else []
    return {"type": rubric_type, "criteria": [item for item in criteria if item is not None]}


def _criterion(value: object, index: int) -> dict[str, Any] | None:
    if isinstance(value, str):
        value = {"label": value}
    if not isinstance(value, dict):
        return None
    label = _text(value.get("label") or value.get("criterion") or value.get("question"))
    if not label:
        return None
    return {
        "id": _text(value.get("id")) or f"RR-{index:02d}",
        "label": label,
        "result": _choice(_text(value.get("result") or value.get("status")).lower(), RUBRIC_RESULTS, "unknown"),
        "evidence": _text_list(value.get("evidence")),
        "assumptions": _text_list(value.get("assumptions")),
        "suggestions": _text_list(value.get("suggestions") or value.get("recommendations")),
    }


def _evidence(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            label = _text(item.get("label") or item.get("source")) or "Evidence"
            detail = _text(item.get("detail") or item.get("note") or item.get("text"))
        else:
            label = "Evidence"
            detail = _text(item)
        if detail:
            result.append({"label": label, "detail": detail})
    return result


def _questions(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            question = _text(item.get("question") or item.get("text"))
            why = _text(item.get("why") or item.get("reason"))
        else:
            question = _text(item)
            why = ""
        if question:
            result.append({"id": f"Q{index}", "question": question, "why": why})
    return result


def _project_todo_cards(value: dict[str, Any], fallback_type: str, optimized: dict[str, Any]) -> list[dict[str, Any]]:
    raw_cards = (
        value.get("project_todo_cards")
        or value.get("recommended_todos")
        or value.get("split_requirements")
        or value.get("cards")
        or []
    )
    cards = [_project_todo_card(item, index, fallback_type) for index, item in enumerate(raw_cards, start=1)] if isinstance(raw_cards, list) else []
    cards = [card for card in cards if card is not None]
    if not cards and optimized["title"]:
        cards.append(_card_from_optimized(optimized))
    return cards


def _project_todo_card(value: object, index: int, fallback_type: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = _text(value.get("title"))
    if not title:
        return None
    todo_type_id = _todo_type_id(value.get("todo_type_id") or value.get("requirement_type") or value.get("type") or fallback_type)
    description = _card_description(value, todo_type_id)
    artifact_kinds = _card_artifact_kinds(value.get("artifact_kinds"), todo_type_id)
    return {
        "id": _text(value.get("id")) or f"REQ-{index:03d}",
        "title": _clip(title, 255),
        "description": _clip(description, 65536),
        "status": _choice(_text(value.get("status")).upper(), {"TODO", "BLOCKED"}, "TODO"),
        "todo_type_id": todo_type_id,
        "artifact_kinds": artifact_kinds,
        "review_strategy": _choice(_text(value.get("review_strategy")).upper(), {"LOCAL_CARD", "GITEA", "GITHUB"}, "LOCAL_CARD"),
    }


def _card_from_optimized(optimized: dict[str, Any]) -> dict[str, Any]:
    value = {
        "id": "REQ-001",
        "title": optimized["title"],
        "description": optimized["description"],
        "todo_type_id": optimized["todo_type_id"],
        "acceptance_criteria": optimized["acceptance_criteria"],
        "non_goals": optimized["non_goals"],
    }
    card = _project_todo_card(value, 1, optimized["todo_type_id"])
    assert card is not None
    return card


def _card_description(value: dict[str, Any], todo_type_id: str) -> str:
    existing = _card_description_text(value.get("description"))
    lines = [
        existing,
    ]
    _append_list(lines, "Evidence", _text_list(value.get("evidence")))
    _append_list(lines, "Assumptions", _text_list(value.get("assumptions")))
    _append_list(lines, "Acceptance criteria", _text_list(value.get("acceptance_criteria") or value.get("criteria")))
    _append_list(lines, "Non-goals", _text_list(value.get("non_goals") or value.get("out_of_scope")))
    _append_list(lines, "Validation notes", _text_list(value.get("test_notes") or value.get("validation")))
    return "\n".join(line for line in lines if line is not None).strip()


def _card_description_text(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    return requirement_review_card_todo_description(text) or ""


def requirement_review_card_todo_description(description: str | None) -> str | None:
    if not description:
        return description
    cleaned = CARD_DESCRIPTION_TYPE_METADATA_RE.sub(" ", description).strip()
    return cleaned or None


def _card_artifact_kinds(value: object, todo_type_id: str) -> list[str]:
    explicit = normalize_project_todo_card_artifact_kinds(_text_list(value))
    if explicit:
        return explicit[:20]
    return list(DEFAULT_ARTIFACT_KINDS_BY_TODO_TYPE.get(todo_type_id, []))


def _todo_type_id(value: object) -> str:
    return normalize_project_todo_card_type_id(value)


def _requirement_type(value: object) -> str:
    raw = _text(value).lower()
    mapped = {
        "debug": "bug",
        "ui-change": "ui",
        "solution-research": "research",
        "performance": "performance-optimization",
        "performance-optimization": "performance-optimization",
        "large": "large-feature",
        "feature": "small-feature",
        "product": "product-design",
    }.get(raw, raw)
    return mapped if mapped in REQUIREMENT_TYPES else "default"


def _render_html(content: dict[str, Any]) -> str:
    criteria = "".join(_criterion_html(item) for item in content["rubric"]["criteria"])
    questions = _list_html([f"{item['question']} ({item['why']})" if item["why"] else item["question"] for item in content["clarifying_questions"]])
    evidence = _evidence_html(content["evidence"])
    cards = "".join(_card_html(card) for card in content["project_todo_cards"])
    card_script = _script_json(content["project_todo_cards"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(content["title"])}</title><style>
:root {{ color-scheme: light; --bg:#f6f8fb; --panel:#fff; --text:#18202a; --muted:#64748b; --border:#d8e0ea; --accent:#0f766e; --warn:#b45309; --bad:#b91c1c; --info:#2563eb; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:28px; }} header,.panel,.card {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; }}
header {{ display:grid; gap:8px; margin-bottom:14px; }} h1 {{ margin:0; font-size:26px; line-height:1.2; }} h2 {{ margin:0 0 10px; font-size:18px; }} h3 {{ margin:0; font-size:15px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }} .stack {{ display:grid; gap:14px; }} .muted {{ color:var(--muted); }} .meta {{ display:flex; gap:6px; flex-wrap:wrap; }}
.pill {{ border:1px solid var(--border); border-radius:999px; background:#eef4f8; padding:2px 8px; font-size:12px; font-weight:700; }} .ready,.pass {{ background:#dcfce7; color:#166534; }} .needs_clarification,.needs_split,.concern,.unknown {{ background:#fef3c7; color:#92400e; }} .too_broad,.not_recommended,.risky,.fail {{ background:#fee2e2; color:#991b1b; }}
.criteria,.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; }} .card {{ display:grid; gap:10px; }} dl {{ display:grid; gap:6px; margin:0; }} dt {{ color:var(--muted); font-weight:700; }} dd {{ margin:0; }} ul {{ margin:6px 0 0; padding-left:18px; }}
button {{ justify-self:start; border:1px solid var(--accent); border-radius:6px; background:var(--accent); color:#fff; padding:6px 10px; font-weight:700; cursor:pointer; }} button:disabled {{ cursor:default; opacity:.72; }}
@media (max-width:760px) {{ main {{ padding:18px; }} h1 {{ font-size:22px; }} .grid {{ grid-template-columns:1fr; }} .criteria,.cards {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
<header><div class="meta"><span class="pill">{escape(content["detected_type"])}</span><span class="pill {escape(content["verdict"])}">{escape(content["verdict"])}</span><span class="pill">{escape(content["confidence"])}</span></div><h1>{escape(content["title"])}</h1><div>{escape(content["executive_summary"])}</div></header>
<section class="grid"><article class="panel"><h2>Optimized Requirement</h2>{_optimized_html(content["optimized_requirement"])}</article><article class="panel"><h2>Clarifying Questions</h2>{questions}</article></section>
<section class="panel"><h2>Rubric</h2><div class="criteria">{criteria or '<div class="muted">No rubric criteria recorded.</div>'}</div></section>
<section class="grid"><article class="panel"><h2>Evidence</h2>{evidence}</article><article class="panel"><h2>Assumptions And Recommendations</h2>{_list_html(content["assumptions"] + content["recommendations"])}</article></section>
<section class="panel"><h2>Candidate Todo Cards</h2><div class="cards">{cards or '<div class="muted">No candidate cards recorded.</div>'}</div></section>
<script type="application/json" id="project-todo-cards">{card_script}</script><script>{_bridge_script()}</script>
</main></body></html>"""


def _criterion_html(item: dict[str, Any]) -> str:
    evidence = _list_html(item["evidence"])
    assumptions = _list_html(item["assumptions"])
    suggestions = _list_html(item["suggestions"])
    return f"""<article class="card"><div class="meta"><span class="pill {escape(item["result"])}">{escape(item["result"])}</span><span class="pill">{escape(item["id"])}</span></div><h3>{escape(item["label"])}</h3><dl><dt>Evidence</dt><dd>{evidence}</dd><dt>Assumptions</dt><dd>{assumptions}</dd><dt>Suggestions</dt><dd>{suggestions}</dd></dl></article>"""


def _optimized_html(item: dict[str, Any]) -> str:
    if not item["title"] and not item["description"]:
        return '<div class="muted">No optimized requirement recorded.</div>'
    return f"""<dl><dt>Title</dt><dd>{escape(item["title"] or "-")}</dd><dt>Todo type</dt><dd>{escape(item["todo_type_id"])}</dd><dt>Description</dt><dd>{escape(item["description"] or "-")}</dd><dt>Acceptance</dt><dd>{_list_html(item["acceptance_criteria"])}</dd><dt>Non-goals</dt><dd>{_list_html(item["non_goals"])}</dd></dl>"""


def _evidence_html(items: list[dict[str, str]]) -> str:
    if not items:
        return '<div class="muted">No evidence recorded.</div>'
    return "<ul>" + "".join(f"<li><strong>{escape(item['label'])}:</strong> {escape(item['detail'])}</li>" for item in items) + "</ul>"


def _card_html(card: dict[str, Any]) -> str:
    return f"""<article class="card"><div class="meta"><span class="pill">{escape(card["todo_type_id"])}</span><span class="pill">{escape(card["status"])}</span><span class="pill">{escape(card["id"])}</span></div><h3>{escape(card["title"])}</h3><p>{escape(card["description"] or "-")}</p><button type="button" data-card-id="{escape(card["id"])}">Add to board</button></article>"""


def _list_html(items: list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return '<span class="muted">None recorded.</span>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in values) + "</ul>"


def _script_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _bridge_script() -> str:
    return """
const cards = JSON.parse(document.getElementById("project-todo-cards")?.textContent || "[]");
const pending = new Map();
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-card-id]");
  if (!button) return;
  const card = cards.find((item) => item.id === button.dataset.cardId);
  if (!card) return;
  const requestId = `requirement-card-${card.id}-${Date.now()}`;
  pending.set(requestId, button);
  button.disabled = true;
  button.textContent = "Adding";
  window.parent.postMessage({
    type: "web-terminal.project-todo.create",
    version: 1,
    request_id: requestId,
    card
  }, "*");
});
window.addEventListener("message", (event) => {
  const message = event.data || {};
  const button = pending.get(message.request_id);
  if (!button) return;
  if (message.type === "web-terminal.project-todo.created") {
    button.textContent = "Added";
    pending.delete(message.request_id);
  }
  if (message.type === "web-terminal.project-todo.create_failed") {
    button.disabled = false;
    button.textContent = "Retry";
    pending.delete(message.request_id);
  }
});
""".strip()
