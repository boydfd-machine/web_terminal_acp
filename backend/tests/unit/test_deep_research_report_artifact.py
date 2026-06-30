from app.artifact_plugins.deep_research_report import DeepResearchReportArtifactPlugin


def test_deep_research_report_prompt_requests_structured_visual_report() -> None:
    plugin = DeepResearchReportArtifactPlugin()

    prompt = plugin.build_prompt(source_title="Deep Research terminal", output_path="/tmp/report.json")

    assert "structured" in prompt.lower()
    assert "sections" in prompt
    assert "comparison_matrix" in prompt
    assert "recommendations" in prompt
    assert "Do not output raw HTML" in prompt
    assert "Do not just convert Markdown syntax to HTML" in prompt
    assert "/tmp/report.json" in prompt


def test_deep_research_report_renders_structured_html_not_markdown_conversion() -> None:
    plugin = DeepResearchReportArtifactPlugin()
    parsed = plugin.parse_output(
        """
{
  "artifact_kind": "deep_research_report",
  "title": "Renderer decision",
  "executive_summary": "Use a structured artifact rather than raw Markdown.",
  "highlights": [
    {"label": "Best fit", "value": "Structured JSON", "detail": "Enables a scannable report UI."}
  ],
  "sections": [
    {
      "title": "Security",
      "takeaway": "Escape all terminal-derived content.",
      "bullets": ["Avoid arbitrary HTML from the agent.", "Keep source Markdown as traceability only."],
      "evidence": ["Existing renderer escaped script tags."]
    }
  ],
  "comparison_matrix": {
    "columns": ["Option", "Strength", "Risk"],
    "rows": [
      {"cells": ["Markdown conversion", "Simple", "Still reads like Markdown"]},
      {"cells": ["Structured artifact", "Scannable", "Needs schema"]}
    ]
  },
  "recommendations": [
    {"priority": "P1", "recommendation": "Ask the agent for structured report data.", "reason": "The UI can render summaries, cards, and tables."}
  ],
  "sources": [{"label": "Renderer docs", "url": "https://example.test/docs", "note": "Compared behavior."}],
  "source_markdown": "# Renderer decision\\n\\nRaw report retained for audit."
}
"""
    )
    rendered = plugin.render(parsed)

    assert rendered.content_json["executive_summary"] == "Use a structured artifact rather than raw Markdown."
    assert rendered.content_json["report_markdown"] == "# Renderer decision\n\nRaw report retained for audit."
    assert rendered.metadata_json == {
        "renderer": "deep-research-report",
        "artifact_kind": "deep_research_report",
    }
    assert "research-highlight-grid" in rendered.display_html
    assert "Structured JSON" in rendered.display_html
    assert "Comparison Matrix" in rendered.display_html
    assert "Markdown conversion" in rendered.display_html
    assert "Ask the agent for structured report data." in rendered.display_html
    assert "<details" in rendered.display_html
    assert "Raw Source Markdown" in rendered.display_html
    assert '<section><h2>Research Analysis</h2><div class="sections"><article><h3>Security</h3>' in rendered.display_html


def test_deep_research_report_keeps_legacy_markdown_as_fallback_source() -> None:
    plugin = DeepResearchReportArtifactPlugin()

    rendered = plugin.render({
        "artifact_kind": "deep_research_report",
        "title": "Legacy report",
        "summary": "Legacy markdown-only artifact.",
        "report_markdown": "# Legacy report\n\n- Escaped <script>alert(1)</script>",
        "sources": ["https://example.test/legacy"],
    })

    assert rendered.content_json["executive_summary"] == "Legacy markdown-only artifact."
    assert rendered.content_json["sections"][0]["title"] == "Legacy report"
    assert "Legacy markdown-only artifact." in rendered.display_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered.display_html
    assert "Raw Source Markdown" in rendered.display_html
