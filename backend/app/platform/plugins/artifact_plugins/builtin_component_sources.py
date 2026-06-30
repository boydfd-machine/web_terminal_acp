from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .agent_pitfalls import AgentPitfallsArtifactPlugin, PITFALL_CLASSIFICATION_GUIDANCE
from .agent_trace_graph import AgentTraceGraphArtifactPlugin, AGENT_TRACE_GRAPH_SKILL_PATH_HINTS
from .acas_project_artifacts import AcasProjectArtifactPlugin
from .builtin_display_templates import (
    deep_research_html_template,
    page_review_html_template,
    pitfalls_html_template,
    requirement_review_html_template,
    review_agent_html_template,
)
from .builtin_preview_fixtures import (
    builtin_preview_content_json,
    builtin_preview_content_json_by_locale,
)
from .deep_research_report import DeepResearchReportArtifactPlugin
from .page_review_cards import PageReviewCardsArtifactPlugin
from .requirement_review_report import RequirementReviewReportArtifactPlugin
from .review_agent_artifacts import ReviewAgentArtifactPlugin
from .trace_template_components import agent_trace_python_source, trace_html_template
from .types import TerminalArtifactPlugin


@dataclass(frozen=True)
class BuiltinArtifactPluginComponents:
    python_source: str
    prompt_template: str
    html_template: str
    json_schema: dict[str, Any]
    preview_content_json: dict[str, Any]


def builtin_artifact_plugin_components(
    plugin: TerminalArtifactPlugin,
) -> BuiltinArtifactPluginComponents | None:
    if isinstance(plugin, AcasProjectArtifactPlugin):
        components = plugin.components()
        return BuiltinArtifactPluginComponents(
            python_source=components.python_source,
            prompt_template=components.prompt_template,
            html_template=components.html_template,
            json_schema=components.json_schema,
            preview_content_json=components.preview_content_json,
        )
    if isinstance(plugin, AgentTraceGraphArtifactPlugin):
        return _agent_trace_components(plugin)
    if isinstance(plugin, AgentPitfallsArtifactPlugin):
        return _components(
            plugin,
            prompt_template=_agent_pitfalls_prompt_template(),
            html_template=pitfalls_html_template(),
            json_schema=_pitfalls_schema(),
            renderer="agent-pitfalls",
        )
    if isinstance(plugin, PageReviewCardsArtifactPlugin):
        return _components(
            plugin,
            prompt_template=_page_review_prompt_template(),
            html_template=page_review_html_template(),
            json_schema=_page_review_schema(),
            renderer="page-review-cards",
        )
    if isinstance(plugin, DeepResearchReportArtifactPlugin):
        return _deep_research_components(plugin)
    if isinstance(plugin, RequirementReviewReportArtifactPlugin):
        return _components(
            plugin,
            prompt_template=_requirement_review_prompt_template(),
            html_template=requirement_review_html_template(),
            json_schema=_requirement_review_schema(),
            renderer="requirement-review-report",
        )
    if isinstance(plugin, ReviewAgentArtifactPlugin):
        spec = plugin._spec
        return _components(
            plugin,
            prompt_template=_review_agent_prompt_template(spec),
            html_template=review_agent_html_template(),
            json_schema=_review_agent_schema(spec),
            renderer="review-agent-qa",
        )
    return None


def _agent_trace_components(plugin: TerminalArtifactPlugin) -> BuiltinArtifactPluginComponents:
    json_schema = _trace_schema()
    return BuiltinArtifactPluginComponents(
        python_source=agent_trace_python_source(plugin),
        prompt_template=_agent_trace_prompt_template().strip() + "\n",
        html_template=trace_html_template().strip() + "\n",
        json_schema=json_schema,
        preview_content_json=builtin_preview_content_json(plugin, json_schema),
    )


def _deep_research_components(plugin: TerminalArtifactPlugin) -> BuiltinArtifactPluginComponents:
    json_schema = _deep_research_schema()
    return BuiltinArtifactPluginComponents(
        python_source=_deep_research_python(plugin),
        prompt_template=_deep_research_prompt_template(),
        html_template=deep_research_html_template().strip() + "\n",
        json_schema=json_schema,
        preview_content_json=builtin_preview_content_json(plugin, json_schema),
    )


def builtin_artifact_plugin_source_body(
    plugin: TerminalArtifactPlugin,
    *,
    fallback_source: str | None,
) -> tuple[str, dict[str, Any]]:
    components = builtin_artifact_plugin_components(plugin)
    if components is None:
        return "legacy_python", {"source": fallback_source, "python_source": fallback_source}
    return (
        "template",
        {
            "source": components.python_source,
            "python_source": components.python_source,
            "prompt_template": components.prompt_template,
            "html_template": components.html_template,
            "json_schema": components.json_schema,
            "preview_content_json": components.preview_content_json,
            "preview_content_json_by_locale": _preview_content_json_by_locale(plugin, components),
        },
    )


def _preview_content_json_by_locale(
    plugin: TerminalArtifactPlugin,
    components: BuiltinArtifactPluginComponents,
) -> dict[str, dict[str, Any]]:
    if isinstance(plugin, AcasProjectArtifactPlugin):
        return {
            "en": components.preview_content_json,
            "zh": components.preview_content_json,
        }
    return builtin_preview_content_json_by_locale(plugin, components.json_schema)


def _components(
    plugin: TerminalArtifactPlugin,
    *,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    renderer: str,
) -> BuiltinArtifactPluginComponents:
    return BuiltinArtifactPluginComponents(
        python_source=_metadata_python(plugin, renderer),
        prompt_template=prompt_template.strip() + "\n",
        html_template=html_template.strip() + "\n",
        json_schema=json_schema,
        preview_content_json=builtin_preview_content_json(plugin, json_schema),
    )


def _metadata_python(plugin: TerminalArtifactPlugin, renderer: str) -> str:
    metadata = {
        "artifact_kind": plugin.artifact_kind,
        "label": plugin.label,
        "default_title": plugin.default_title,
        "renderer": renderer,
    }
    return f'''ARTIFACT_KIND = {json.dumps(metadata["artifact_kind"])}
LABEL = {json.dumps(metadata["label"])}
DEFAULT_TITLE = {json.dumps(metadata["default_title"])}


def metadata_json(content):
    return {{"renderer": {json.dumps(metadata["renderer"])}, "artifact_kind": ARTIFACT_KIND}}
'''.strip() + "\n"


def _agent_trace_prompt_template() -> str:
    hints = ", ".join(AGENT_TRACE_GRAPH_SKILL_PATH_HINTS)
    return f"""请先读取并遵循 agent-trace-graph skill 的 SKILL.md 指令；如果当前 agent-client 没有自动加载该 skill，请优先尝试这些路径: {hints}。 基于当前已经恢复/复制的 session 上下文，为 terminal “{{{{ source_title }}}}” 的这次探索/执行过程生成 artifact JSON。只输出一份合法 JSON，不要输出 Markdown fenced code，不要渲染 HTML，不要截图。JSON 必须包含 task、goals、nodes、edges，且 deadend 节点不能再有 tried/leads-to 出边。不要在字符串字段里嵌入原始 JSON；如果要提到命令输出，用自然语言摘要或转义后的字符串。{{{{ output_instruction }}}} 输出完成后停止。{{% if user_prompt %}} 用户补充要求: {{{{ user_prompt }}}}{{% endif %}}"""


def _agent_pitfalls_prompt_template() -> str:
    return (
        "生成 agent 通用避坑 artifact。只记录跨任务可复用、会浪费 token/tool call/等待时间的坑。"
        "不要复盘当前任务细节，除非它能作为通用坑的证据。"
        "可参考当前已经恢复/复制的 session 上下文和 terminal “{{ source_title }}”，"
        "但 artifact 必须面向以后任何任务都可能再踩的模式。"
        "每条坑必须给出更省 token 的替代动作，以及解决方案类型。"
        "解决方案优先级固定为：install_software > update_memory > add_skill > add_tool。"
        f"{PITFALL_CLASSIFICATION_GUIDANCE}"
        "只输出合法 JSON，不要输出 Markdown fenced code，不要渲染 HTML，不要截图。"
        "JSON schema: {{ json_schema_text }} solution 可以是对象、字符串或字符串数组，但必须具体可执行。"
        "priority 按省 token 收益排序；不要输出空 pitfalls，若没有足够证据也要记录可从上下文确认的通用坑。"
        "{{ output_instruction }} 输出完成后停止。{% if user_prompt %} 用户补充要求: {{ user_prompt }}{% endif %}"
    )


def _page_review_prompt_template() -> str:
    return """Review the page or product flow represented by terminal "{{ source_title }}" and generate a page_review_cards artifact. Use the deep-research skill when current UX, accessibility, performance, browser, or platform guidance matters. Evaluate interaction design, experience friction, feature enhancements, bugs, accessibility, and performance. Ground UX findings in NN/g usability heuristics, accessibility findings in WCAG 2.2, performance findings in Core Web Vitals, and implementation requests in user-story plus acceptance-criteria form. Output requirement cards that can be added directly to project todos. Each card must be independently actionable, evidence-backed, priority-ranked, and retestable. If evidence is missing, state the unknown instead of inventing it.{{ output_instruction }} Output only valid JSON. Do not output Markdown fences, HTML, or screenshots. JSON shape: {{ json_schema_text }}. Stop after producing the artifact.{% if user_prompt %} User requirements: {{ user_prompt }}{% endif %}"""


def _review_agent_prompt_template(spec: Any) -> str:
    references = "; ".join(f"{item['label']} ({item['url']})" for item in spec.references)
    return f"""Generate a review-agent QA artifact of kind {spec.artifact_kind} for terminal "{{{{ source_title }}}}". Purpose: {spec.purpose} Best presentation: {spec.presentation} Required sections: {", ".join(spec.sections)}. Each item should use these fields when relevant: {", ".join(spec.item_fields)}. Keep the artifact actionable for engineers: include concrete evidence, unknowns, owners, and retest actions. If evidence is missing, mark status unknown instead of inventing results. Research basis: {references}. Output only valid JSON. Do not output Markdown fences, HTML, or screenshots. JSON shape: {{{{ json_schema_text }}}}.{{{{ output_instruction }}}} Stop after producing the artifact.{{% if user_prompt %}} User requirements: {{{{ user_prompt }}}}{{% endif %}}"""


def _deep_research_prompt_template() -> str:
    return """Convert the final deep research result from terminal "{{ source_title }}" into a structured, visual deep_research_report artifact. Read the completed research report from the current/resumed session context, then redesign it into scannable sections, highlights, a comparison_matrix when options are compared, and actionable recommendations. Do not just convert Markdown syntax to HTML. Preserve citations, source URLs, tables, caveats, and decision-relevant evidence in structured fields. If useful, keep the raw final Markdown in source_markdown for audit only.{{ output_instruction }} Output only valid JSON. Do not output raw HTML, Markdown fences, or screenshots. JSON shape: {{ json_schema_text }}. Stop after producing the artifact.{% if user_prompt %} User requirements: {{ user_prompt }}{% endif %}"""


def _requirement_review_prompt_template() -> str:
    return """Generate a requirement_review_report artifact for terminal "{{ source_title }}". Review the source project todo requirement, not the implementation. Do not modify the original todo, do not automatically block dispatch, and do not implement code. Classify the requirement type, then apply a type-specific rubric: bug/debug requires reproduction, expected vs actual, impact, and regression signal; UI requires target flow, states, responsive/accessibility evidence, and design-system fit; research requires decision question, options, constraints, credible sources, and recommendation criteria; large-feature requires user value, scope boundaries, dependencies, architecture fit, staged delivery, and acceptance; performance requires metric, baseline, budget, bottleneck hypothesis, correctness guard, and regression check. Split every conclusion into evidence, assumptions, and recommendations. Produce project_todo_cards for optimized or split follow-up requirements; each card must be independently actionable and set a suitable built-in todo_type_id. Use BLOCKED only when the card cannot start until a named clarification is answered.{{ output_instruction }} Output only valid JSON. Do not output Markdown fences, HTML, or screenshots. JSON shape: {{ json_schema_text }}. Stop after producing the artifact.{% if user_prompt %} User requirements: {{ user_prompt }}{% endif %}"""


def _deep_research_python(plugin: TerminalArtifactPlugin) -> str:
    return f'''ARTIFACT_KIND = {json.dumps(plugin.artifact_kind)}
LABEL = {json.dumps(plugin.label)}
DEFAULT_TITLE = {json.dumps(plugin.default_title)}

from app.platform.plugins.artifact_plugins.deep_research_report import _markdown_html, normalize_deep_research_report


def normalize_content(content):
    return normalize_deep_research_report(content)


def template_context(content):
    return {{"source_markdown_html": _markdown_html(content.get("report_markdown", ""))}}


def metadata_json(content):
    return {{"renderer": "deep-research-report", "artifact_kind": ARTIFACT_KIND}}
'''.strip() + "\n"


def _trace_schema() -> dict[str, Any]:
    return {"type": "object", "required": ["task", "goals", "nodes", "edges"], "properties": {"task": {"type": "string"}, "goals": {"type": "array"}, "nodes": {"type": "array"}, "edges": {"type": "array"}}, "additionalProperties": True}


def _pitfalls_schema() -> dict[str, Any]:
    return {"type": "object", "required": ["pitfalls"], "properties": {"artifact_kind": {"const": "agent_pitfalls"}, "title": {"type": "string"}, "pitfalls": {"type": "array", "minItems": 1, "items": {"type": "object"}}}, "additionalProperties": True}


def _page_review_schema() -> dict[str, Any]:
    return {"type": "object", "required": ["cards"], "properties": {"artifact_kind": {"const": "page_review_cards"}, "title": {"type": "string"}, "page": {"type": "string"}, "review_scope": {"type": "string"}, "executive_summary": {"type": "string"}, "cards": {"type": "array", "minItems": 1, "items": {"type": "object"}}, "references": {"type": "array"}}, "additionalProperties": True}


def _review_agent_schema(spec: Any) -> dict[str, Any]:
    return {"type": "object", "required": ["sections"], "properties": {"artifact_kind": {"const": spec.artifact_kind}, "title": {"type": "string"}, "target": {"type": "string"}, "review_scope": {"type": "string"}, "executive_summary": {"type": "string"}, "presentation": {"type": "object"}, "sections": {"type": "array", "minItems": 1, "items": {"type": "object"}}, "decisions": {"type": "array"}, "references": {"type": "array"}}, "additionalProperties": True}


def _deep_research_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "anyOf": [
            {"required": ["sections"]},
            {"required": ["source_markdown"]},
            {"required": ["report_markdown"]},
        ],
        "properties": {
            "artifact_kind": {"const": "deep_research_report"},
            "title": {"type": "string"},
            "executive_summary": {"type": "string"},
            "summary": {"type": "string"},
            "highlights": {"type": "array", "items": {"type": "object"}},
            "sections": {"type": "array", "minItems": 1, "items": {"type": "object"}},
            "comparison_matrix": {"type": "object"},
            "recommendations": {"type": "array", "items": {"type": "object"}},
            "source_markdown": {"type": "string"},
            "report_markdown": {"type": "string", "minLength": 1},
            "key_findings": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": True,
    }


def _requirement_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["executive_summary"],
        "properties": {
            "artifact_kind": {"const": "requirement_review_report"},
            "title": {"type": "string"},
            "source_requirement": {"type": "object"},
            "detected_type": {"type": "string"},
            "verdict": {"type": "string"},
            "confidence": {"type": "string"},
            "executive_summary": {"type": "string"},
            "rubric": {"type": "object"},
            "evidence": {"type": "array", "items": {"type": "object"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "clarifying_questions": {"type": "array", "items": {"type": "object"}},
            "optimized_requirement": {"type": "object"},
            "recommendations": {"type": "array", "items": {"type": "string"}},
            "recommended_next_step": {"type": "string"},
            "project_todo_cards": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": True,
    }
