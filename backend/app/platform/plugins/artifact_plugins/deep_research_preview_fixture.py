from __future__ import annotations

from typing import Any


def deep_research_preview(locale: str) -> dict[str, Any]:
    if locale == "zh":
        return _deep_research_preview_zh()
    return _deep_research_preview()


def _deep_research_preview() -> dict[str, Any]:
    return {
        "artifact_kind": "deep_research_report",
        "locale": "en",
        "title": "Artifact preview renderer research",
        "executive_summary": "Structured HTML previews make JSON-based artifacts easier to inspect in settings.",
        "highlights": [
            {
                "label": "Best fit",
                "value": "Structured JSON",
                "detail": "Settings can render scannable cards, tables, and source links.",
            },
            {
                "label": "Preview risk",
                "value": "Raw JSON is hard to review",
                "detail": "Large nested arrays hide priorities and decision evidence.",
            },
        ],
        "sections": [
            {
                "title": "Renderer Contract",
                "takeaway": "Agent output stays JSON while settings previews use artifact-specific HTML.",
                "bullets": [
                    "Tables render as responsive HTML tables instead of raw JSON arrays.",
                    "Decision-heavy artifacts expose summary, evidence, and source links first.",
                ],
                "evidence": [
                    "Template preview rendering validates JSON schema before producing HTML.",
                    "The same content JSON remains available for agent and API consumers.",
                ],
            },
            {
                "title": "Human Review",
                "takeaway": "The preview should reveal the artifact's intended reading pattern.",
                "bullets": [
                    "QA reports read best as evidence tables.",
                    "Page review cards read best as priority boards.",
                    "Research reports read best as structured analysis with an optional source appendix.",
                ],
                "evidence": ["Settings users need to inspect the display result before installing a template."],
            },
        ],
        "comparison_matrix": {
            "columns": ["Artifact", "Preferred display", "Reason"],
            "rows": [
                {"cells": ["QA reports", "Evidence tables", "Reviewers scan status, owner, and retest actions."]},
                {"cells": ["Page review cards", "Priority board", "Requirement cards map to implementation todos."]},
                {"cells": ["Research reports", "Structured report", "Highlights, matrices, and links preserve the research narrative."]},
            ],
        },
        "recommendations": [
            {
                "priority": "P1",
                "recommendation": "Use artifact-specific HTML templates for built-in settings previews.",
                "reason": "Each artifact has a different natural inspection pattern.",
            },
            {
                "priority": "P2",
                "recommendation": "Retain source Markdown as an audit appendix for research artifacts.",
                "reason": "The structured display remains scannable without losing citations or caveats.",
            },
        ],
        "source_markdown": "\n".join([
            "# Artifact preview renderer research",
            "",
            "## Recommendation",
            "Use artifact-specific HTML templates for settings previews while keeping agent output as JSON.",
            "",
            "| Artifact | Preferred display | Reason |",
            "| --- | --- | --- |",
            "| QA reports | Evidence tables | Reviewers scan status, owner, and retest actions. |",
            "| Page review cards | Priority board | Requirement cards map naturally to implementation todos. |",
            "| Research reports | Markdown report | Headings, tables, and links preserve the research narrative. |",
            "",
            "## Implementation Notes",
            "- Keep preview fixtures representative of real generated output.",
            "- Escape user content before rendering links, tables, and code blocks.",
            "- Avoid embedding raw JSON blocks in the human-facing preview.",
            "",
            "Reference: https://example.test/artifact-preview-guidance",
        ]),
        "sources": [
            {
                "label": "Preview guidance",
                "url": "https://example.test/artifact-preview-guidance",
                "note": "Example source used by the preview fixture.",
            },
        ],
    }


def _deep_research_preview_zh() -> dict[str, Any]:
    return {
        "artifact_kind": "deep_research_report",
        "locale": "zh",
        "title": "Artifact 预览渲染研究",
        "executive_summary": "结构化 HTML 预览能让基于 JSON 的 artifact 在设置页更容易检查。",
        "highlights": [
            {
                "label": "最佳形态",
                "value": "结构化 JSON",
                "detail": "设置页可以渲染可扫描的卡片、表格和来源链接。",
            },
            {
                "label": "预览风险",
                "value": "原始 JSON 很难评审",
                "detail": "大型嵌套数组会隐藏优先级和决策证据。",
            },
        ],
        "sections": [
            {
                "title": "渲染契约",
                "takeaway": "Agent 输出保持 JSON，设置页预览使用按 artifact 定制的 HTML。",
                "bullets": [
                    "表格内容渲染为响应式 HTML 表格，而不是原始 JSON 数组。",
                    "决策型 artifact 优先展示摘要、证据和来源链接。",
                ],
                "evidence": [
                    "模板预览会先验证 JSON schema，再生成 HTML。",
                    "同一份 content JSON 仍可供 agent 和 API 消费。",
                ],
            },
            {
                "title": "人工评审",
                "takeaway": "预览应该呈现 artifact 最自然的阅读方式。",
                "bullets": [
                    "QA 报告适合证据表格。",
                    "页面评审卡片适合优先级看板。",
                    "研究报告适合结构化分析，并保留可选来源附录。",
                ],
                "evidence": ["设置页用户需要在安装模板前检查最终展示效果。"],
            },
        ],
        "comparison_matrix": {
            "columns": ["Artifact", "推荐展示", "原因"],
            "rows": [
                {"cells": ["QA 报告", "证据表格", "Review 人员需要快速扫描状态、负责人和复测动作。"]},
                {"cells": ["页面评审卡片", "优先级看板", "需求卡片天然对应可执行 todo。"]},
                {"cells": ["研究报告", "结构化报告", "重点、矩阵和链接能保留研究叙事。"]},
            ],
        },
        "recommendations": [
            {
                "priority": "P1",
                "recommendation": "为内置 artifact 设置页预览使用专用 HTML 模板。",
                "reason": "每类 artifact 都有不同的自然检查方式。",
            },
            {
                "priority": "P2",
                "recommendation": "研究类 artifact 保留源 Markdown 作为审计附录。",
                "reason": "结构化展示保持可扫描，同时不丢失引用和边界条件。",
            },
        ],
        "source_markdown": "\n".join([
            "# Artifact 预览渲染研究",
            "",
            "## 建议",
            "在设置页预览中使用按 artifact 定制的 HTML 模板，同时保持 agent 输出为 JSON。",
            "",
            "| Artifact | 推荐展示 | 原因 |",
            "| --- | --- | --- |",
            "| QA 报告 | 证据表格 | Review 人员需要快速扫描状态、负责人和复测动作。 |",
            "| 页面评审卡片 | 优先级看板 | 需求卡片天然对应可执行 todo。 |",
            "| 研究报告 | Markdown 报告 | 标题、表格和链接能保留研究叙事。 |",
            "",
            "## 实现说明",
            "- 预览 fixture 要接近真实生成结果。",
            "- 渲染链接、表格和代码块前必须转义用户内容。",
            "- 不要在人类预览中嵌入原始 JSON 块。",
            "",
            "参考: https://example.test/artifact-preview-guidance",
        ]),
        "sources": [
            {
                "label": "预览指南",
                "url": "https://example.test/artifact-preview-guidance",
                "note": "预览 fixture 使用的示例来源。",
            },
        ],
    }
