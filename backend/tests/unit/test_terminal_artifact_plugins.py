from pathlib import Path

import pytest

from app.artifact_plugins.agent_pitfalls import AgentPitfallsArtifactPlugin
from app.artifact_plugins.agent_trace_graph import AgentTraceGraphArtifactPlugin
from app.artifact_plugins.deep_research_report import DeepResearchReportArtifactPlugin
from app.artifact_plugins.review_agent_artifacts import (
    REVIEW_AGENT_QA_ARTIFACT_SPECS,
    ReviewAgentArtifactPlugin,
)
from app.platform.plugins.artifact_plugins.page_review_cards import (
    PageReviewCardsArtifactPlugin,
    page_review_card_todo_payload,
)
from app.artifact_plugins.registry import (
    TerminalArtifactPluginRegistry,
    get_terminal_artifact_plugin_registry,
)
from app.platform.plugins.artifact_plugins.builtin_component_sources import (
    builtin_artifact_plugin_components,
)


def test_agent_trace_graph_plugin_extracts_json_from_terminal_output(tmp_path: Path) -> None:
    plugin = AgentTraceGraphArtifactPlugin(render_script=tmp_path / "missing-render.py")
    payload = {
        "task": "demo",
        "goals": [{"id": "g1", "label": "Goal"}],
        "nodes": [{"id": "n1", "type": "goal", "label": "Done", "goal": "g1", "status": "success"}],
        "edges": [],
    }

    parsed = plugin.parse_output(f"thinking...\n{payload!r}\n".replace("'", '"'))

    assert parsed["task"] == "demo"
    assert parsed["nodes"][0]["id"] == "n1"


def test_agent_trace_graph_plugin_repairs_wrapped_terminal_json(tmp_path: Path) -> None:
    plugin = AgentTraceGraphArtifactPlugin(render_script=tmp_path / "missing-render.py")
    output = """
• {
  "task": "terminal “空会话与问候”探索/执行过程 artifact JSON",
  "goals": [
  {
  "id": "g1",
  "label": "目标: 复盘空会话与问候问题"
  }
  ],
  "nodes": [
  {
  "id": "n1",
  "type": "decision",
  "label": "读取恢复/复制的 session 上下文",
  "goal": "g1",
  "step": 1,
  "status": "neutral",
  "detail": "从当前已恢复/复制的上下文切入，确认任务主题是 terminal 空会话与问
  候，并且需要生成 agent-trace-graph artifact JSON。"
  }
  ],
  "edges": []
  }
"""

    parsed = plugin.parse_output(output)

    assert parsed["task"].startswith("terminal")
    assert "agent-trace-graph artifact JSON" in parsed["nodes"][0]["detail"]


def test_agent_trace_graph_plugin_repairs_wrapped_json_with_raw_json_inside_string(tmp_path: Path) -> None:
    plugin = AgentTraceGraphArtifactPlugin(render_script=tmp_path / "missing-render.py")
    output = """
• {"task":"terminal “空会话与问候”探索/执行过程 artifact JSON","goals":
  [{"id":"g1","label":"目标: 读取 skill 并恢复上下文"}],"nodes":
  [{"id":"n1","type":"action","label":"验证 parser 保存 artifact
  JSON","goal":"g1","step":1,"status":"success","detail":"运行本地临时 SQLite
  验证。命令输出为
  {"parser_save_verified": true, "task": "terminal 空会话与问候 artifact parser
  保存验证"}。"}],"edges":[]}
"""

    parsed = plugin.parse_output(output)

    assert parsed["task"].startswith("terminal")
    assert parsed["nodes"][0]["detail"].startswith("运行本地临时 SQLite")
    assert "parser_save_verified" in parsed["nodes"][0]["detail"]


def test_agent_trace_graph_plugin_prompt_names_skill_paths() -> None:
    plugin = AgentTraceGraphArtifactPlugin()

    prompt = plugin.build_prompt(source_title="Demo terminal")

    assert "agent-trace-graph" in prompt
    assert "~/.claude/skills/agent-trace-graph/SKILL.md" in prompt
    assert "$CODEX_HOME/skills/agent-trace-graph/SKILL.md" in prompt
    assert "$CURSOR_AGENT_HOME/skills-cursor/agent-trace-graph/SKILL.md" in prompt
    assert "$WEB_TERMINAL_CODEX_HOME/skills/agent-trace-graph/SKILL.md" in prompt
    assert "$WEB_TERMINAL_CURSOR_HOME/skills-cursor/agent-trace-graph/SKILL.md" in prompt
    assert "只输出一份合法 JSON" in prompt
    assert "不要在字符串字段里嵌入原始 JSON" in prompt


def test_agent_trace_graph_plugin_prompt_writes_json_to_output_path() -> None:
    plugin = AgentTraceGraphArtifactPlugin()

    prompt = plugin.build_prompt(source_title="Demo terminal", output_path="/tmp/artifact.json")

    assert "/tmp/artifact.json" in prompt
    assert "不要把 JSON 输出到聊天窗口" in prompt
    assert "mv" in prompt
    assert "一次性写入" in prompt


def test_agent_trace_graph_plugin_renders_node_details_in_modal_only() -> None:
    plugin = AgentTraceGraphArtifactPlugin()

    rendered = plugin.render({
        "task": "Trace <unsafe>",
        "goals": [{"id": "g1", "label": "Goal"}],
        "nodes": [
            {
                "id": "n1",
                "type": "action",
                "label": "Inspect output",
                "goal": "g1",
                "step": 1,
                "status": "success",
                "detail": "No permanent detail panel should be visible.",
            }
        ],
        "edges": [],
    })

    assert rendered.metadata_json == {
        "renderer": "agent-trace-graph",
        "artifact_kind": "agent_trace_graph",
    }
    assert "<svg" in rendered.display_html
    assert "trace-node-modal" in rendered.display_html
    assert 'role="dialog"' in rendered.display_html
    assert "← 点击节点查看详情" not in rendered.display_html
    assert 'id="panel"' not in rendered.display_html
    visible_markup = rendered.display_html.split('<script type="application/json" id="trace-node-data">', 1)[0]
    assert "No permanent detail panel should be visible." not in visible_markup
    assert "No permanent detail panel should be visible." in rendered.display_html
    assert "No permanent detail panel should be visible." in rendered.content_json["nodes"][0]["detail"]


def test_agent_trace_graph_plugin_reports_missing_renderer(tmp_path: Path) -> None:
    plugin = AgentTraceGraphArtifactPlugin(render_script=tmp_path / "missing-render.py")

    with pytest.raises(ValueError, match="renderer not found"):
        plugin.render({"task": "demo", "goals": [], "nodes": [], "edges": []})


def test_agent_pitfalls_plugin_prompt_enforces_token_saving_scope() -> None:
    plugin = AgentPitfallsArtifactPlugin()

    prompt = plugin.build_prompt(source_title="Demo terminal", output_path="/tmp/pitfalls.json")

    assert "agent 通用避坑 artifact" in prompt
    assert "跨任务可复用" in prompt
    assert "install_software > update_memory > add_skill > add_tool" in prompt
    assert "solution_type 必须按根因分类" in prompt
    assert "fresh frontend worktree 缺 node_modules" in prompt
    assert "先猜 npm script 名" in prompt
    assert "更新哪个 skill" in prompt
    assert "新增自动化工具或 API 集成" in prompt
    assert "只输出合法 JSON" in prompt
    assert "/tmp/pitfalls.json" in prompt
    assert "不要把 JSON 输出到聊天窗口" in prompt


def test_agent_pitfalls_builtin_template_matches_prompt_classification_guidance() -> None:
    components = builtin_artifact_plugin_components(AgentPitfallsArtifactPlugin())

    assert components is not None
    assert "solution_type 必须按根因分类" in components.prompt_template
    assert "fresh frontend worktree 缺 node_modules" in components.prompt_template
    assert "更新哪个 skill" in components.prompt_template


def test_agent_pitfalls_plugin_extracts_and_normalizes_json() -> None:
    plugin = AgentPitfallsArtifactPlugin()
    output = """
thinking...
{
  "artifact_kind": "agent_pitfalls",
  "title": "Pitfalls",
  "pitfalls": [
    {
      "pitfall": "  Missing jq  ",
      "wasted_action": "run jq and fail",
      "why_it_wastes_tokens": "extra tool call",
      "better_action": "install jq first",
      "solution_type": "install_software",
      "solution": {"install": "sudo apt-get install -y jq", "verify": "jq --version"},
      "priority": "high"
    },
    {
      "pitfall": "Local typo",
      "wasted_action": "fix one local function",
      "why_it_wastes_tokens": "not reusable",
      "better_action": "",
      "solution_type": "update_memory",
      "solution": "skip",
      "priority": "low"
    }
  ]
}
"""

    parsed = plugin.parse_output(output)

    assert parsed["artifact_kind"] == "agent_pitfalls"
    assert parsed["title"] == "Pitfalls"
    assert parsed["pitfalls"] == [
        {
            "pitfall": "Missing jq",
            "wasted_action": "run jq and fail",
            "why_it_wastes_tokens": "extra tool call",
            "better_action": "install jq first",
            "solution_type": "install_software",
            "solution": {"install": "sudo apt-get install -y jq", "verify": "jq --version"},
            "priority": "high",
        }
    ]


def test_agent_pitfalls_plugin_repairs_wrapped_terminal_json() -> None:
    plugin = AgentPitfallsArtifactPlugin()
    output = """
• {"artifact_kind":"agent_pitfalls","title":"Agent token-saving pitfalls","pitfalls":
  [{"pitfall":"执行系统中缺失的命令","wasted_action":"直接运行 tree
  后失败","why_it_wastes_tokens":"失败命令消耗一次 tool call，还要再判断替代方案",
  "better_action":"先用 rg --files；确实高频需要目录树再安装 tree",
  "solution_type":"install_software","solution":{"install":"sudo apt-get
  install -y tree","verify":"tree --version"},"priority":"high"}]}
"""

    parsed = plugin.parse_output(output)

    assert parsed["pitfalls"][0]["pitfall"] == "执行系统中缺失的命令"
    assert parsed["pitfalls"][0]["solution"]["install"].startswith("sudo apt-get")


def test_agent_pitfalls_plugin_renders_grouped_escaped_html() -> None:
    plugin = AgentPitfallsArtifactPlugin()

    rendered = plugin.render({
        "title": "Pitfalls <unsafe>",
        "pitfalls": [
            {
                "pitfall": "Missing <jq>",
                "wasted_action": "run jq",
                "why_it_wastes_tokens": "fails once",
                "better_action": "install jq",
                "solution_type": "install_software",
                "solution": {"install": "sudo apt-get install -y jq"},
                "priority": "high",
            },
            {
                "pitfall": "Wrong search habit",
                "wasted_action": "use find first",
                "why_it_wastes_tokens": "slower output",
                "better_action": "use rg --files",
                "solution_type": "update_memory",
                "solution": "Write AGENTS.md note",
                "priority": "medium",
            },
        ],
    })

    assert rendered.metadata_json == {"renderer": "agent-pitfalls"}
    assert rendered.content_json["artifact_kind"] == "agent_pitfalls"
    assert "Install Software" in rendered.display_html
    assert "Update Memory" in rendered.display_html
    assert "Pitfalls &lt;unsafe&gt;" in rendered.display_html
    assert "Missing &lt;jq&gt;" in rendered.display_html
    assert "<jq>" not in rendered.display_html


def test_page_review_cards_plugin_renders_escaped_todo_ready_cards() -> None:
    plugin = PageReviewCardsArtifactPlugin()

    rendered = plugin.render({
        "artifact_kind": "page_review_cards",
        "title": "Review <settings>",
        "page": "/settings",
        "review_scope": "Settings page empty state",
        "executive_summary": "One actionable improvement.",
        "cards": [
            {
                "id": "PRC-001",
                "title": "Clarify empty state",
                "type": "interaction",
                "priority": "P1",
                "severity": "high",
                "user_value": "Users know the next action.",
                "problem": "The panel is blank.",
                "proposal": "Show an empty state with a primary action.",
                "evidence": [{"label": "Observation", "detail": "Blank settings panel"}],
                "acceptance_criteria": ["Empty state names the next action."],
                "test_notes": ["Open settings with no configured data."],
            }
        ],
    })

    assert rendered.metadata_json == {
        "renderer": "page-review-cards",
        "artifact_kind": "page_review_cards",
    }
    assert rendered.content_json["artifact_kind"] == "page_review_cards"
    assert "Review &lt;settings&gt;" in rendered.display_html
    assert "Clarify empty state" in rendered.display_html
    assert "Blank settings panel" in rendered.display_html
    assert "<settings>" not in rendered.display_html


def test_page_review_card_todo_payload_formats_requirement_card() -> None:
    title, description = page_review_card_todo_payload(
        {
            "artifact_kind": "page_review_cards",
            "title": "Page review",
            "page": "/settings",
            "cards": [
                {
                    "id": "PRC-001",
                    "title": "Clarify empty state",
                    "type": "interaction",
                    "priority": "P1",
                    "severity": "high",
                    "user_value": "Users know how to continue.",
                    "problem": "No empty state explains the missing settings.",
                    "proposal": "Add an empty state with a primary setup action.",
                    "evidence": [{"label": "Observation", "detail": "Blank panel"}],
                    "acceptance_criteria": ["Primary setup action is visible."],
                    "test_notes": ["Load settings with no data."],
                }
            ],
        },
        "PRC-001",
    )

    assert title == "[P1] Clarify empty state"
    assert "Card id: PRC-001" in description
    assert "Proposal:\nAdd an empty state with a primary setup action." in description
    assert "- Primary setup action is visible." in description


def test_default_terminal_artifact_registry_includes_agent_pitfalls() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: agent_pitfalls"):
        get_terminal_artifact_plugin_registry().by_kind("agent_pitfalls")


def test_default_terminal_artifact_registry_includes_review_agent_qa_artifacts() -> None:
    registry = get_terminal_artifact_plugin_registry()

    for spec in REVIEW_AGENT_QA_ARTIFACT_SPECS:
        with pytest.raises(ValueError, match=f"unsupported terminal artifact kind: {spec.artifact_kind}"):
            registry.by_kind(spec.artifact_kind)


def test_default_terminal_artifact_registry_includes_page_review_cards() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: page_review_cards"):
        get_terminal_artifact_plugin_registry().by_kind("page_review_cards")


def test_deep_research_report_plugin_extracts_markdown_and_renders_html() -> None:
    plugin = DeepResearchReportArtifactPlugin()
    output = """
thinking...
{
  "artifact_kind": "deep_research_report",
  "title": "Renderer comparison",
  "summary": "Mistune and markdown-it are viable.",
  "report_markdown": "# Renderer comparison\\n\\n- **Mistune** supports tables.\\n- Visit https://example.test/docs.\\n\\n| Option | Note |\\n| --- | --- |\\n| mistune | Fast |\\n\\n<script>alert(1)</script>",
  "key_findings": ["Tables need responsive overflow."],
  "sources": [{"label": "Docs", "url": "https://example.test/docs", "note": "API reference"}]
}
"""

    parsed = plugin.parse_output(output)
    rendered = plugin.render(parsed)

    assert parsed["artifact_kind"] == "deep_research_report"
    assert parsed["report_markdown"].startswith("# Renderer comparison")
    assert rendered.metadata_json == {
        "renderer": "deep-research-report",
        "artifact_kind": "deep_research_report",
    }
    assert "<h1>Renderer comparison</h1>" in rendered.display_html
    assert "<table>" in rendered.display_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered.display_html
    assert '<a href="https://example.test/docs"' in rendered.display_html


def test_default_terminal_artifact_registry_includes_deep_research_report() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: deep_research_report"):
        get_terminal_artifact_plugin_registry().by_kind("deep_research_report")


def test_review_agent_qa_artifact_prompt_names_format_and_sources() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: qa_accessibility_audit"):
        get_terminal_artifact_plugin_registry().by_kind("qa_accessibility_audit")
    plugin = next(
        ReviewAgentArtifactPlugin(spec)
        for spec in REVIEW_AGENT_QA_ARTIFACT_SPECS
        if spec.artifact_kind == "qa_accessibility_audit"
    )

    prompt = plugin.build_prompt(
        source_title="Demo terminal",
        output_path="/tmp/qa-accessibility.json",
    )

    assert "qa_accessibility_audit" in prompt
    assert "WCAG" in prompt
    assert "sections" in prompt
    assert "/tmp/qa-accessibility.json" in prompt
    assert "Do not print JSON to chat" in prompt


def test_review_agent_qa_artifact_extracts_and_renders_html() -> None:
    with pytest.raises(ValueError, match="unsupported terminal artifact kind: qa_release_readiness"):
        get_terminal_artifact_plugin_registry().by_kind("qa_release_readiness")
    plugin = next(
        ReviewAgentArtifactPlugin(spec)
        for spec in REVIEW_AGENT_QA_ARTIFACT_SPECS
        if spec.artifact_kind == "qa_release_readiness"
    )
    output = """
thinking...
{
  "artifact_kind": "qa_release_readiness",
  "title": "Release readiness",
  "target": "Todo review flow",
  "review_scope": "Local regression and review evidence",
  "executive_summary": "One blocker remains.",
  "sections": [
    {
      "title": "Release gates",
      "intent": "Show ship criteria",
      "columns": ["id", "gate", "current_status", "decision"],
      "items": [
        {
          "id": "G1",
          "gate": "Regression",
          "current_status": "Failed on mobile",
          "decision": "warn"
        }
      ]
    }
  ],
  "decisions": [
    {
      "label": "Ship decision",
      "status": "warn",
      "rationale": "Mobile evidence is incomplete.",
      "next_action": "Run mobile compatibility pass."
    }
  ],
  "references": [
    {
      "label": "QA deliverables",
      "url": "https://example.test/qa",
      "note": "Demo reference"
    }
  ]
}
"""

    parsed = plugin.parse_output(output)
    rendered = plugin.render(parsed)

    assert parsed["artifact_kind"] == "qa_release_readiness"
    assert parsed["sections"][0]["items"][0]["gate"] == "Regression"
    assert rendered.metadata_json == {
        "renderer": "review-agent-qa",
        "artifact_kind": "qa_release_readiness",
    }
    assert "Release readiness" in rendered.display_html
    assert "Ship decision" in rendered.display_html
    assert "Regression" in rendered.display_html


def test_terminal_artifact_plugin_registry_rejects_duplicate_kinds() -> None:
    first = AgentTraceGraphArtifactPlugin()
    second = AgentTraceGraphArtifactPlugin()

    with pytest.raises(ValueError, match="duplicate terminal artifact plugin kind"):
        TerminalArtifactPluginRegistry((first, second))
