from __future__ import annotations

import json
from html import escape
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .review_agent_artifact_specs import REVIEW_AGENT_QA_ARTIFACT_SPECS, ReviewAgentArtifactSpec
from .types import TerminalArtifactRender


class ReviewAgentArtifactPlugin:
    def __init__(self, spec: ReviewAgentArtifactSpec) -> None:
        self._spec = spec
        self.artifact_kind = spec.artifact_kind
        self.label = spec.label
        self.default_title = spec.default_title

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
            "target": "feature, flow, PR, or release under review",
            "review_scope": "what was reviewed and what evidence was available",
            "executive_summary": "short QA conclusion",
            "presentation": {"primary": self._spec.presentation, "why": "why this format helps reviewers"},
            "sections": [
                {
                    "title": "one of the required section names",
                    "intent": "why this section exists",
                    "columns": list(self._spec.item_fields),
                    "items": [{"field": "use the requested item fields; keep values concrete"}],
                }
            ],
            "decisions": [
                {
                    "label": "gate, priority, or follow-up",
                    "status": "pass|warn|fail|unknown",
                    "rationale": "evidence-backed reason",
                    "next_action": "specific next action",
                }
            ],
            "references": [{"label": "source name", "url": "https://...", "note": "how it informed this artifact"}],
        }
        prompt = (
            f"Generate a review-agent QA artifact of kind {self.artifact_kind} for terminal \"{source_title}\"."
            f" Purpose: {self._spec.purpose}"
            f" Best presentation: {self._spec.presentation}"
            f" Required sections: {', '.join(self._spec.sections)}."
            f" Each item should use these fields when relevant: {', '.join(self._spec.item_fields)}."
            " Keep the artifact actionable for engineers: include concrete evidence, unknowns, owners, and retest actions."
            " If evidence is missing, mark status unknown instead of inventing results."
            f" Research basis: {_reference_text(self._spec.references)}."
            " Output only valid JSON. Do not output Markdown fences, HTML, or screenshots."
            f" JSON shape: {json.dumps(schema, ensure_ascii=True)}."
            f"{output_instruction}"
            " Stop after producing the artifact."
            f"{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        last_error = ""
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                normalized = _normalize_review_artifact(candidate, self._spec)
            except ValueError as exc:
                last_error = str(exc)
                continue
            if normalized is not None:
                return normalized
        detail = f": {last_error}" if last_error else ""
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output{detail}")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = _normalize_review_artifact(content_json, self._spec)
        if normalized is None:
            raise ValueError(f"invalid {self.artifact_kind} JSON")
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=_render_review_artifact_html(normalized),
            metadata_json={"renderer": "review-agent-qa", "artifact_kind": self.artifact_kind},
        )


def review_agent_artifact_plugins() -> tuple[ReviewAgentArtifactPlugin, ...]:
    return tuple(ReviewAgentArtifactPlugin(spec) for spec in REVIEW_AGENT_QA_ARTIFACT_SPECS)


def _normalize_review_artifact(value: dict[str, Any], spec: ReviewAgentArtifactSpec) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    artifact_kind = _text(value.get("artifact_kind"))
    if artifact_kind and artifact_kind != spec.artifact_kind:
        return None
    sections = _normalize_sections(value.get("sections"), spec)
    if not sections:
        raise ValueError("sections must include at least one non-empty section")
    return {
        "artifact_kind": spec.artifact_kind,
        "title": _text(value.get("title")) or spec.default_title,
        "target": _text(value.get("target")) or "Current review target",
        "review_scope": _text(value.get("review_scope")) or "Scope not specified",
        "executive_summary": _text(value.get("executive_summary")) or "No summary provided.",
        "presentation": _normalize_presentation(value.get("presentation"), spec),
        "sections": sections,
        "decisions": _normalize_decisions(value.get("decisions")),
        "references": _normalize_references(value.get("references"), spec.references),
    }


def _normalize_sections(value: object, spec: ReviewAgentArtifactSpec) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sections: list[dict[str, Any]] = []
    for index, section in enumerate(value, start=1):
        if not isinstance(section, dict):
            continue
        items = _normalize_items(section.get("items"))
        if not items:
            continue
        columns = _normalize_columns(section.get("columns"), items, spec.item_fields)
        title = _text(section.get("title")) or _default_section_title(spec, index)
        sections.append(
            {
                "title": title,
                "intent": _text(section.get("intent")),
                "view": _text(section.get("view")) or spec.presentation,
                "columns": columns,
                "items": items,
            }
        )
    return sections


def _normalize_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {str(key).strip(): val for key, val in item.items() if str(key).strip()}
        if normalized:
            items.append(normalized)
    return items


def _default_section_title(spec: ReviewAgentArtifactSpec, index: int) -> str:
    if index <= len(spec.sections):
        return spec.sections[index - 1]
    return f"Section {index}"


def _normalize_columns(value: object, items: list[dict[str, Any]], default_fields: tuple[str, ...]) -> list[str]:
    columns = [_text(item) for item in value] if isinstance(value, list) else []
    columns = [column for column in columns if column]
    if not columns:
        item_keys = [key for item in items for key in item.keys()]
        columns = [field for field in default_fields if field in item_keys]
    if not columns and items:
        columns = list(items[0].keys())
    return _dedupe(columns)[:10]


def _normalize_presentation(value: object, spec: ReviewAgentArtifactSpec) -> dict[str, str]:
    if isinstance(value, dict):
        primary = _text(value.get("primary")) or spec.presentation
        why = _text(value.get("why")) or "Matches the evidence reviewers need for this QA artifact."
        return {"primary": primary, "why": why}
    return {"primary": spec.presentation, "why": "Matches the evidence reviewers need for this QA artifact."}


def _normalize_decisions(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    decisions: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        status = _status(item.get("status"))
        decisions.append(
            {
                "label": _text(item.get("label")) or "Decision",
                "status": status,
                "rationale": _text(item.get("rationale")),
                "next_action": _text(item.get("next_action")),
            }
        )
    return decisions


def _normalize_references(value: object, defaults: tuple[dict[str, str], ...]) -> list[dict[str, str]]:
    references = value if isinstance(value, list) and value else list(defaults)
    normalized: list[dict[str, str]] = []
    for item in references:
        if not isinstance(item, dict):
            continue
        label = _text(item.get("label"))
        url = _text(item.get("url"))
        if not label and not url:
            continue
        normalized.append({"label": label or url, "url": url, "note": _text(item.get("note"))})
    return normalized


def _render_review_artifact_html(content: dict[str, Any]) -> str:
    sections = "\n".join(_render_section(section) for section in content["sections"])
    decisions = _render_decisions(content["decisions"])
    references = _render_references(content["references"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(content["title"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f9fb;
      --panel: #fff;
      --text: #18202a;
      --muted: #617083;
      --border: #d7dee8;
      --pass: #047857;
      --warn: #b45309;
      --fail: #b91c1c;
      --unknown: #475569;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    header {{ display: grid; gap: 10px; margin-bottom: 18px; }}
    h1 {{ margin: 0; font-size: 26px; line-height: 1.2; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .muted {{ color: var(--muted); }}
    .summary, .section, .decision, .references {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }}
    .summary-grid, .decisions {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .sections {{ display: grid; gap: 14px; margin-top: 14px; }}
    .badge {{ display: inline-flex; border-radius: 999px; padding: 3px 8px; color: #fff; font-size: 11px; font-weight: 750; }}
    .pass {{ background: var(--pass); }}
    .warn {{ background: var(--warn); }}
    .fail {{ background: var(--fail); }}
    .unknown {{ background: var(--unknown); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 7px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; background: #fff; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; background: #eef3f8; }}
    tr:last-child td {{ border-bottom: 0; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    .references {{ margin-top: 14px; }}
    .references ul {{ margin: 8px 0 0; padding-left: 18px; }}
    @media (max-width: 720px) {{
      main {{ padding: 18px; }}
      h1 {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escape(content["title"])}</h1>
      <div class="muted">{escape(content["artifact_kind"])} / {escape(content["target"])}</div>
    </header>
    <section class="summary">
      <div class="summary-grid">
        <div><h3>Summary</h3><div>{escape(content["executive_summary"])}</div></div>
        <div><h3>Scope</h3><div>{escape(content["review_scope"])}</div></div>
        <div><h3>Presentation</h3><div>{escape(content["presentation"]["primary"])}</div><div class="muted">{escape(content["presentation"]["why"])}</div></div>
      </div>
    </section>
    {decisions}
    <div class="sections">{sections}</div>
    {references}
  </main>
</body>
</html>"""


def _render_decisions(decisions: list[dict[str, str]]) -> str:
    if not decisions:
        return ""
    cards = "\n".join(
        f"""<article class="decision">
  <h3>{escape(item["label"])} <span class="badge {escape(item["status"])}">{escape(item["status"])}</span></h3>
  <div>{escape(item["rationale"])}</div>
  <div class="muted">{escape(item["next_action"])}</div>
</article>"""
        for item in decisions
    )
    return f'<section class="decisions" aria-label="Decisions">{cards}</section>'


def _render_section(section: dict[str, Any]) -> str:
    columns = section["columns"]
    header = "".join(f"<th>{escape(_label(column))}</th>" for column in columns)
    rows = "\n".join(_render_row(item, columns) for item in section["items"])
    intent = f'<div class="muted">{escape(section["intent"])}</div>' if section["intent"] else ""
    return f"""<section class="section">
  <h2>{escape(section["title"])}</h2>
  {intent}
  <div class="table-wrap">
    <table>
      <thead><tr>{header}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>"""


def _render_row(item: dict[str, Any], columns: list[str]) -> str:
    cells = "".join(f"<td>{_render_cell(item.get(column, ''))}</td>" for column in columns)
    return f"<tr>{cells}</tr>"


def _render_cell(value: object) -> str:
    if isinstance(value, (dict, list)):
        return "<pre>" + escape(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre>"
    return escape(_text(value))


def _render_references(references: list[dict[str, str]]) -> str:
    if not references:
        return ""
    items = "\n".join(
        f'<li><a href="{escape(item["url"])}">{escape(item["label"])}</a> <span class="muted">{escape(item["note"])}</span></li>'
        if item["url"]
        else f'<li>{escape(item["label"])} <span class="muted">{escape(item["note"])}</span></li>'
        for item in references
    )
    return f'<section class="references"><h2>References</h2><ul>{items}</ul></section>'


def _reference_text(references: tuple[dict[str, str], ...]) -> str:
    return "; ".join(f"{item['label']} ({item['url']})" for item in references)


def _status(value: object) -> str:
    status = _text(value).lower()
    return status if status in {"pass", "warn", "fail", "unknown"} else "unknown"


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
