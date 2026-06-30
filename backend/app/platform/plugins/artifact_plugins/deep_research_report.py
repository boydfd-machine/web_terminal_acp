from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .types import TerminalArtifactRender

_URL = re.compile(r"https?://[^\s<>()]+")


class DeepResearchReportArtifactPlugin:
    artifact_kind = "deep_research_report"
    label = "Deep Research Report"
    default_title = "Deep research report"

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
            "executive_summary": "one-paragraph executive summary",
            "highlights": [
                {"label": "metric or theme", "value": "short value", "detail": "why it matters"}
            ],
            "sections": [
                {
                    "title": "section heading",
                    "takeaway": "main point",
                    "bullets": ["scannable detail"],
                    "evidence": ["supporting evidence or caveat"],
                }
            ],
            "comparison_matrix": {
                "columns": ["Option", "Strength", "Risk"],
                "rows": [{"cells": ["option name", "strength", "risk"]}],
            },
            "recommendations": [
                {"priority": "P1", "recommendation": "actionable recommendation", "reason": "rationale"}
            ],
            "sources": [{"label": "source title", "url": "https://...", "note": "how it was used"}],
            "source_markdown": "optional raw final Markdown report retained for audit",
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
            f"Convert the final deep research result from terminal \"{source_title}\" into a structured,"
            f" visual {self.artifact_kind} artifact. Read the completed research report from the"
            " current/resumed session context, then redesign it into scannable sections, highlights,"
            " a comparison_matrix when options are compared, and actionable recommendations."
            " Do not just convert Markdown syntax to HTML. Preserve citations, source URLs, tables,"
            " caveats, and decision-relevant evidence in the structured fields. If useful, keep the raw"
            " final Markdown in source_markdown for audit only. If there are multiple drafts, use the"
            " latest complete report. Output only valid JSON matching this shape: "
            f"{json.dumps(schema, ensure_ascii=True)}."
            " Do not output raw HTML or Markdown fences."
            f"{output_instruction} Stop after producing the artifact.{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        last_error = ""
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                return normalize_deep_research_report(candidate)
            except ValueError as exc:
                last_error = str(exc)
        detail = f": {last_error}" if last_error else ""
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output{detail}")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = normalize_deep_research_report(content_json)
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=_render_html(normalized),
            metadata_json={
                "renderer": "deep-research-report",
                "artifact_kind": self.artifact_kind,
            },
        )


def normalize_deep_research_report(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("artifact content must be an object")
    artifact_kind = _text(value.get("artifact_kind"))
    if artifact_kind and artifact_kind != DeepResearchReportArtifactPlugin.artifact_kind:
        raise ValueError("artifact_kind does not match deep_research_report")
    markdown = _raw_text(
        value.get("source_markdown")
        or value.get("report_markdown")
        or value.get("markdown")
        or value.get("report")
        or value.get("content")
    ).strip()
    title = _text(value.get("title")) or _title_from_markdown(markdown) or DeepResearchReportArtifactPlugin.default_title
    summary = _text(value.get("executive_summary") or value.get("summary"))
    sections = _sections(value.get("sections"))
    key_findings = _text_list(value.get("key_findings") or value.get("findings"))
    if not sections and markdown:
        sections = _legacy_sections(markdown, title=title, key_findings=key_findings)
    if not sections and not summary:
        raise ValueError("deep research report must include structured sections or source markdown")
    return {
        "artifact_kind": DeepResearchReportArtifactPlugin.artifact_kind,
        "title": title,
        "executive_summary": summary,
        "summary": summary,
        "highlights": _highlights(value.get("highlights"), key_findings),
        "sections": sections,
        "comparison_matrix": _comparison_matrix(value.get("comparison_matrix") or value.get("comparison")),
        "recommendations": _recommendations(value.get("recommendations")),
        "sources": _sources(value.get("sources")),
        "report_markdown": markdown,
    }


def _render_html(content: dict[str, Any]) -> str:
    highlights = "".join(_highlight_html(item) for item in content["highlights"])
    highlight_section = f'<section class="research-highlight-grid">{highlights}</section>' if highlights else ""
    sections = "".join(_section_html(section) for section in content["sections"])
    matrix = _matrix_html(content["comparison_matrix"])
    recommendations = "".join(_recommendation_html(item) for item in content["recommendations"])
    recommendation_section = (
        f"<section><h2>Recommendations</h2><div class=\"recommendations\">{recommendations}</div></section>"
        if recommendations
        else ""
    )
    sources = "".join(_source_html(source) for source in content["sources"])
    sources_section = f"<section><h2>Sources</h2><ul class=\"source-list\">{sources}</ul></section>" if sources else ""
    raw_markdown = _raw_markdown_details(content["report_markdown"])
    summary = f"<p class=\"summary\">{_inline(content['executive_summary'])}</p>" if content["executive_summary"] else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(content["title"])}</title><style>
body{{margin:0;background:#f6f8fb;color:#18202a;font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1120px;margin:0 auto;padding:30px}}section,article,details{{background:#fff;border:1px solid #d7dee8;border-radius:8px;padding:16px;margin-top:14px}}
h1{{font-size:30px;line-height:1.2;margin:0 0 8px}}h2{{font-size:18px;margin:0 0 10px}}h3{{font-size:15px;margin:0 0 8px}}
.summary{{color:#526173;font-size:16px;max-width:860px}}.research-highlight-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}
.highlight,.recommendation{{border:1px solid #d7dee8;border-radius:8px;padding:12px;background:#f9fbfd}}.highlight strong{{display:block;font-size:20px;margin:3px 0}}
.sections{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}ul{{padding-left:20px}}pre{{overflow:auto;background:#0f172a;color:#e2e8f0;border-radius:6px;padding:12px}}
code{{background:#eef2f7;border-radius:4px;padding:1px 4px}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;min-width:560px}}
th,td{{border:1px solid #d7dee8;padding:8px 10px;text-align:left;vertical-align:top}}th{{background:#eef3f8;color:#617083;font-size:12px;text-transform:uppercase}}
.priority{{display:inline-block;border-radius:999px;background:#1f2937;color:#fff;padding:2px 8px;font-size:12px;font-weight:750}}a{{color:#0369a1}}</style></head><body><main>
<h1>{escape(content["title"])}</h1>{summary}{highlight_section}
<section><h2>Research Analysis</h2><div class="sections">{sections}</div></section>{matrix}
{recommendation_section}{sources_section}{raw_markdown}
</main></body></html>"""


def _highlight_html(item: dict[str, str]) -> str:
    label = f"<span>{_inline(item['label'])}</span>" if item.get("label") else ""
    detail = f"<small>{_inline(item['detail'])}</small>" if item.get("detail") else ""
    return f"<article class=\"highlight\">{label}<strong>{_inline(item['value'])}</strong>{detail}</article>"


def _section_html(section: dict[str, Any]) -> str:
    bullets = "".join(f"<li>{_inline(item)}</li>" for item in section["bullets"])
    evidence = "".join(f"<li>{_inline(item)}</li>" for item in section["evidence"])
    evidence_html = f"<h3>Evidence</h3><ul>{evidence}</ul>" if evidence else ""
    takeaway = f"<p>{_inline(section['takeaway'])}</p>" if section["takeaway"] else ""
    return f"<article><h3>{_inline(section['title'])}</h3>{takeaway}<ul>{bullets}</ul>{evidence_html}</article>"


def _matrix_html(matrix: dict[str, Any]) -> str:
    columns = matrix.get("columns") or []
    rows = matrix.get("rows") or []
    if not columns or not rows:
        return ""
    head = "".join(f"<th>{_inline(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row["cells"]) + "</tr>"
        for row in rows
    )
    return f'<section><h2>Comparison Matrix</h2><div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></section>'


def _recommendation_html(item: dict[str, str]) -> str:
    reason = f"<p>{_inline(item['reason'])}</p>" if item.get("reason") else ""
    return f'<article class="recommendation"><span class="priority">{_inline(item["priority"])}</span><h3>{_inline(item["recommendation"])}</h3>{reason}</article>'


def _raw_markdown_details(markdown: str) -> str:
    if not markdown:
        return ""
    return f"<details><summary>Raw Source Markdown</summary>{_markdown_html(markdown)}</details>"

def _markdown_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    in_code = False
    code: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            html.append(f"</{list_tag}>")
            list_tag = None

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                html.append(f"<pre><code>{escape(chr(10).join(code))}</code></pre>")
                code.clear()
                in_code = False
            else:
                flush_paragraph()
                close_list()
                in_code = True
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            close_list()
        elif stripped.startswith("#"):
            flush_paragraph()
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            html.append(f"<h{level}>{_inline(stripped[level:].strip())}</h{level}>")
        elif _is_table(lines, index):
            flush_paragraph()
            close_list()
            table, index = _table_html(lines, index)
            html.append(table)
            continue
        elif stripped.startswith(">"):
            flush_paragraph()
            close_list()
            html.append(f"<blockquote>{_inline(stripped.lstrip('> ').strip())}</blockquote>")
        elif stripped.startswith(("- ", "* ")):
            flush_paragraph()
            if list_tag != "ul":
                close_list()
                list_tag = "ul"
                html.append("<ul>")
            html.append(f"<li>{_inline(stripped[2:].strip())}</li>")
        elif re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            if list_tag != "ol":
                close_list()
                list_tag = "ol"
                html.append("<ol>")
            item_text = re.sub(r"^\d+\.\s+", "", stripped)
            html.append(f"<li>{_inline(item_text)}</li>")
        else:
            close_list()
            paragraph.append(stripped)
        index += 1
    flush_paragraph()
    close_list()
    if code:
        html.append(f"<pre><code>{escape(chr(10).join(code))}</code></pre>")
    return "\n".join(html)


def _is_table(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = lines[index].strip()
    separator = lines[index + 1].strip()
    return (
        header.startswith("|")
        and header.endswith("|")
        and separator.startswith("|")
        and separator.endswith("|")
        and set(separator.replace("|", "").replace(":", "").replace("-", "").strip()) == set()
    )


def _table_html(lines: list[str], index: int) -> tuple[str, int]:
    header = _table_cells(lines[index])
    rows: list[list[str]] = []
    index += 2
    while index < len(lines) and lines[index].strip().startswith("|") and lines[index].strip().endswith("|"):
        rows.append(_table_cells(lines[index]))
        index += 1
    head_html = "".join(f"<th>{_inline(cell)}</th>" for cell in header)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>", index


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]

def _inline(value: object) -> str:
    text = escape(_raw_text(value))
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    links: list[str] = []

    def hold_link(match: re.Match[str]) -> str:
        links.append(_markdown_link(match))
        return f"@@DEEP_RESEARCH_LINK_{len(links) - 1}@@"

    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", hold_link, text)
    text = _URL.sub(_bare_link, text)
    for index, link in enumerate(links):
        text = text.replace(f"@@DEEP_RESEARCH_LINK_{index}@@", link)
    return text


def _markdown_link(match: re.Match[str]) -> str:
    label = match.group(1)
    url = _clean_url(match.group(2))
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{label}</a>'


def _bare_link(match: re.Match[str]) -> str:
    url = _clean_url(match.group(0))
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{escape(url)}</a>'


def _clean_url(url: str) -> str:
    return url.rstrip(".,);")

def _source_html(source: dict[str, str]) -> str:
    label = _inline(source.get("label") or source.get("url") or "Source")
    url = _clean_url(source.get("url", ""))
    note = f" <span>{_inline(source['note'])}</span>" if source.get("note") else ""
    if url.startswith(("http://", "https://")):
        return f'<li><a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{label}</a>{note}</li>'
    return f"<li>{label}{note}</li>"


def _sources(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    sources: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            label = _text(item.get("label") or item.get("title") or item.get("name"))
            url = _text(item.get("url") or item.get("href"))
            note = _text(item.get("note") or item.get("description"))
            if label or url or note:
                sources.append({"label": label, "url": url, "note": note})
        elif isinstance(item, str) and item.strip():
            sources.append({"label": item.strip(), "url": "", "note": ""})
    return sources

def _sections(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sections: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title") or item.get("heading")) or f"Section {index}"
        takeaway = _text(item.get("takeaway") or item.get("summary"))
        bullets = _text_list(item.get("bullets") or item.get("points") or item.get("findings"))
        evidence = _text_list(item.get("evidence") or item.get("citations") or item.get("caveats"))
        if takeaway or bullets or evidence:
            sections.append({
                "title": title,
                "takeaway": takeaway,
                "bullets": bullets,
                "evidence": evidence,
            })
    return sections


def _legacy_sections(markdown: str, *, title: str, key_findings: list[str]) -> list[dict[str, Any]]:
    bullets = key_findings or _markdown_bullets(markdown)
    if not bullets:
        bullets = [markdown[:600]]
    return [{
        "title": title,
        "takeaway": "",
        "bullets": bullets,
        "evidence": [],
    }]

def _markdown_bullets(markdown: str) -> list[str]:
    bullets: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            bullets.append(_text(stripped[2:]))
        elif re.match(r"^\d+\.\s+", stripped):
            bullets.append(_text(re.sub(r"^\d+\.\s+", "", stripped)))
    return bullets

def _highlights(value: object, key_findings: list[str]) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                label = _text(item.get("label") or item.get("title"))
                highlight_value = _text(item.get("value") or item.get("finding") or item.get("summary"))
                detail = _text(item.get("detail") or item.get("description") or item.get("note"))
                if highlight_value:
                    highlights.append({"label": label, "value": highlight_value, "detail": detail})
            elif text := _text(item):
                highlights.append({"label": "", "value": text, "detail": ""})
    if highlights:
        return highlights
    return [{"label": "Finding", "value": finding, "detail": ""} for finding in key_findings[:4]]


def _comparison_matrix(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"columns": [], "rows": []}
    columns = _text_list(value.get("columns") or value.get("headers"))
    rows: list[dict[str, list[str]]] = []
    raw_rows = value.get("rows")
    if isinstance(raw_rows, list):
        for row in raw_rows:
            cells = _row_cells(row, columns)
            if cells:
                rows.append({"cells": cells})
    return {"columns": columns, "rows": rows}


def _row_cells(row: object, columns: list[str]) -> list[str]:
    if isinstance(row, dict):
        raw_cells = row.get("cells")
        if isinstance(raw_cells, list):
            return _text_list(raw_cells)
        if columns:
            return [_text(row.get(column) or row.get(column.lower()) or "") for column in columns]
    if isinstance(row, list):
        return _text_list(row)
    return []


def _recommendations(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    recommendations: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            recommendation = _text(item.get("recommendation") or item.get("action") or item.get("title"))
            reason = _text(item.get("reason") or item.get("rationale") or item.get("detail"))
            priority = _text(item.get("priority")) or f"P{index}"
        else:
            recommendation = _text(item)
            reason = ""
            priority = f"P{index}"
        if recommendation:
            recommendations.append({
                "priority": priority,
                "recommendation": recommendation,
                "reason": reason,
            })
    return recommendations


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return _text(stripped.lstrip("#").strip())
    return ""


def _text(value: object) -> str:
    return " ".join(_raw_text(value).split())


def _raw_text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
