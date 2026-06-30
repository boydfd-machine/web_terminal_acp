from __future__ import annotations

import json
from html import escape
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .types import TerminalArtifactRender

CARD_TYPES = {"interaction", "enhancement", "bug", "accessibility", "performance", "content", "security"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
SEVERITIES = {"critical", "high", "medium", "low"}


class PageReviewCardsArtifactPlugin:
    artifact_kind = "page_review_cards"
    label = "Page Review Cards"
    default_title = "Page review requirement cards"

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        extra = f" User requirements: {_single_line(user_prompt)}" if user_prompt else ""
        output_instruction = ""
        if output_path:
            temp_path = f"{output_path}.tmp"
            output_instruction = (
                f" Do not print JSON to chat. Write the final valid JSON to {output_path}."
                f" Prefer writing {temp_path}, validating it, then mv {temp_path} {output_path} atomically."
                " After saving, reply only: artifact JSON saved."
            )
        schema = {
            "artifact_kind": self.artifact_kind,
            "title": self.default_title,
            "page": "page, URL, screen, or user flow reviewed",
            "review_scope": "what was inspected and what evidence was available",
            "executive_summary": "short synthesis of the strongest opportunities",
            "cards": [
                {
                    "id": "PRC-001",
                    "title": "requirement-card title",
                    "type": "interaction|enhancement|bug|accessibility|performance|content|security",
                    "priority": "P0|P1|P2|P3",
                    "severity": "critical|high|medium|low",
                    "user_value": "who benefits and why",
                    "problem": "evidence-backed current issue or opportunity",
                    "proposal": "specific product or implementation change",
                    "evidence": [{"label": "observation, screenshot, metric, or source", "detail": "concrete evidence"}],
                    "acceptance_criteria": ["testable outcome"],
                    "test_notes": ["manual or automated validation step"],
                }
            ],
            "references": [{"label": "source", "url": "https://...", "note": "how it informed the review"}],
        }
        prompt = (
            f"Review the page or product flow represented by terminal \"{source_title}\" and generate"
            f" a {self.artifact_kind} artifact. Use the deep-research skill when current UX, accessibility,"
            " performance, browser, or platform guidance matters. Evaluate interaction design, experience"
            " friction, feature enhancements, bugs, accessibility, and performance. Ground UX findings in"
            " NN/g usability heuristics, accessibility findings in WCAG 2.2, performance findings in Core"
            " Web Vitals, and implementation requests in user-story plus acceptance-criteria form."
            " Output requirement cards that can be added directly to project todos. Each card must be"
            " independently actionable, evidence-backed, priority-ranked, and retestable. If evidence is"
            " missing, state the unknown instead of inventing it."
            f"{output_instruction}"
            " Output only valid JSON. Do not output Markdown fences, HTML, or screenshots."
            f" JSON shape: {json.dumps(schema, ensure_ascii=True)}."
            " Stop after producing the artifact."
            f"{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        last_error = ""
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                return normalize_page_review_cards(candidate)
            except ValueError as exc:
                last_error = str(exc)
        detail = f": {last_error}" if last_error else ""
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output{detail}")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = normalize_page_review_cards(content_json)
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=_render_html(normalized),
            metadata_json={"renderer": "page-review-cards", "artifact_kind": self.artifact_kind},
        )


def normalize_page_review_cards(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("artifact content must be an object")
    artifact_kind = _text(value.get("artifact_kind"))
    if artifact_kind and artifact_kind != PageReviewCardsArtifactPlugin.artifact_kind:
        raise ValueError("artifact_kind does not match page_review_cards")
    cards = [_normalize_card(card, index) for index, card in enumerate(value.get("cards") or [], start=1)]
    cards = [card for card in cards if card is not None]
    if not cards:
        raise ValueError("cards must include at least one requirement card")
    return {
        "artifact_kind": PageReviewCardsArtifactPlugin.artifact_kind,
        "title": _text(value.get("title")) or PageReviewCardsArtifactPlugin.default_title,
        "page": _text(value.get("page")) or "Current page or flow",
        "review_scope": _text(value.get("review_scope")) or "Scope not specified",
        "executive_summary": _text(value.get("executive_summary")) or "No summary provided.",
        "cards": cards,
        "references": _normalize_references(value.get("references")),
    }


def page_review_card_todo_payload(content: dict[str, Any], card_id: str) -> tuple[str, str]:
    normalized = normalize_page_review_cards(content)
    target = next((card for card in normalized["cards"] if card["id"] == card_id), None)
    if target is None:
        raise KeyError(card_id)
    title = _clip(f"[{target['priority']}] {target['title']}", 255)
    description = _todo_description(normalized, target)
    return title, description


def _normalize_card(value: object, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = _text(value.get("title"))
    problem = _text(value.get("problem"))
    proposal = _text(value.get("proposal"))
    if not title or not (problem or proposal):
        return None
    card_type = _choice(_text(value.get("type")).lower(), CARD_TYPES, "enhancement")
    priority = _choice(_text(value.get("priority")).upper(), PRIORITIES, "P2")
    severity = _choice(_text(value.get("severity")).lower(), SEVERITIES, "medium")
    return {
        "id": _text(value.get("id")) or f"PRC-{index:03d}",
        "title": title,
        "type": card_type,
        "priority": priority,
        "severity": severity,
        "user_value": _text(value.get("user_value")),
        "problem": problem,
        "proposal": proposal,
        "evidence": _normalize_evidence(value.get("evidence")),
        "acceptance_criteria": _text_list(value.get("acceptance_criteria")),
        "test_notes": _text_list(value.get("test_notes")),
    }


def _todo_description(artifact: dict[str, Any], card: dict[str, Any]) -> str:
    lines = [
        f"Source artifact: {artifact['title']}",
        f"Page/flow: {artifact['page']}",
        f"Card id: {card['id']}",
        f"Type: {card['type']}",
        f"Priority: {card['priority']}",
        f"Severity: {card['severity']}",
        "",
        "User value:",
        card["user_value"] or "-",
        "",
        "Problem:",
        card["problem"] or "-",
        "",
        "Proposal:",
        card["proposal"] or "-",
    ]
    _append_list(lines, "Evidence", [f"{item['label']}: {item['detail']}" for item in card["evidence"]])
    _append_list(lines, "Acceptance criteria", card["acceptance_criteria"])
    _append_list(lines, "Test notes", card["test_notes"])
    return _clip("\n".join(lines).strip(), 65536)


def _render_html(content: dict[str, Any]) -> str:
    cards = "\n".join(_render_card(card) for card in content["cards"])
    references = _render_references(content["references"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(content["title"])}</title><style>
:root {{ color-scheme: light; --bg:#f6f8fb; --panel:#fff; --text:#18202a; --muted:#64748b; --border:#d8e0ea; --accent:#0f766e; --bug:#b91c1c; --perf:#7c3aed; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:28px; }} header {{ display:grid; gap:8px; margin-bottom:16px; }} h1 {{ margin:0; font-size:26px; line-height:1.2; }} h2 {{ margin:0; font-size:18px; }}
.muted {{ color:var(--muted); }} .summary,.card,.refs {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; }}
.summary {{ margin-bottom:14px; }} .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; }}
.card {{ display:grid; gap:10px; }} .meta {{ display:flex; flex-wrap:wrap; gap:6px; }} .pill {{ border:1px solid var(--border); border-radius:999px; padding:2px 8px; font-size:12px; font-weight:700; background:#eef4f8; }}
.priority {{ background:#0f766e; color:#fff; border-color:#0f766e; }} .severity {{ background:#f8fafc; }} .bug {{ color:var(--bug); }} .performance {{ color:var(--perf); }}
dl {{ display:grid; gap:6px; margin:0; }} dt {{ color:var(--muted); font-weight:700; }} dd {{ margin:0; }} ul {{ margin:6px 0 0; padding-left:18px; }} .refs {{ margin-top:14px; }}
@media (max-width:720px) {{ main {{ padding:18px; }} h1 {{ font-size:22px; }} .cards {{ grid-template-columns:1fr; }} }}
</style></head><body><main><header><h1>{escape(content["title"])}</h1><div class="muted">{escape(content["page"])} / {len(content["cards"])} cards</div></header><section class="summary"><strong>Summary</strong><div>{escape(content["executive_summary"])}</div><div class="muted">{escape(content["review_scope"])}</div></section><section class="cards">{cards}</section>{references}</main></body></html>"""


def _render_card(card: dict[str, Any]) -> str:
    evidence = _render_list([f"{item['label']}: {item['detail']}" for item in card["evidence"]])
    criteria = _render_list(card["acceptance_criteria"])
    tests = _render_list(card["test_notes"])
    return f"""<article class="card" data-card-id="{escape(card["id"])}"><div class="meta"><span class="pill priority">{escape(card["priority"])}</span><span class="pill severity">{escape(card["severity"])}</span><span class="pill {escape(card["type"])}">{escape(card["type"])}</span><span class="pill">{escape(card["id"])}</span></div><h2>{escape(card["title"])}</h2><dl><dt>User value</dt><dd>{escape(card["user_value"] or "-")}</dd><dt>Problem</dt><dd>{escape(card["problem"] or "-")}</dd><dt>Proposal</dt><dd>{escape(card["proposal"] or "-")}</dd><dt>Evidence</dt><dd>{evidence}</dd><dt>Acceptance</dt><dd>{criteria}</dd><dt>Retest</dt><dd>{tests}</dd></dl></article>"""


def _normalize_evidence(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            label = _text(item.get("label")) or "Evidence"
            detail = _text(item.get("detail")) or _text(item.get("note"))
        else:
            label = "Evidence"
            detail = _text(item)
        if detail:
            result.append({"label": label, "detail": detail})
    return result


def _normalize_references(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    references = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _text(item.get("label"))
        url = _text(item.get("url"))
        note = _text(item.get("note"))
        if label or url:
            references.append({"label": label or url, "url": url, "note": note})
    return references


def _render_references(references: list[dict[str, str]]) -> str:
    if not references:
        return ""
    items = "\n".join(
        f'<li><a href="{escape(item["url"])}">{escape(item["label"])}</a> <span class="muted">{escape(item["note"])}</span></li>'
        if item["url"]
        else f'<li>{escape(item["label"])} <span class="muted">{escape(item["note"])}</span></li>'
        for item in references
    )
    return f'<section class="refs"><h2>References</h2><ul>{items}</ul></section>'


def _render_list(items: list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return "-"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in values) + "</ul>"


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    values = [item for item in items if item]
    if not values:
        return
    lines.extend(["", f"{title}:"])
    lines.extend(f"- {item}" for item in values)


def _text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _choice(value: str, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _clip(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max(0, max_length - 1)].rstrip() + "..."


def _text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
