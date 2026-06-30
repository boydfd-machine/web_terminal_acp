from __future__ import annotations

from typing import Any

from .agent_pitfalls import AgentPitfallsArtifactPlugin
from .agent_trace_graph import AgentTraceGraphArtifactPlugin
from .deep_research_report import DeepResearchReportArtifactPlugin
from .deep_research_preview_fixture import deep_research_preview
from .page_review_cards import PageReviewCardsArtifactPlugin
from .preview_data import default_preview_content_json
from .requirement_review_preview_fixture import requirement_review_preview
from .requirement_review_report import RequirementReviewReportArtifactPlugin
from .review_agent_artifacts import ReviewAgentArtifactPlugin
from .types import TerminalArtifactPlugin


def builtin_preview_content_json(plugin: TerminalArtifactPlugin, json_schema: dict[str, Any]) -> dict[str, Any]:
    return builtin_preview_content_json_by_locale(plugin, json_schema)["en"]


def builtin_preview_content_json_by_locale(
    plugin: TerminalArtifactPlugin,
    json_schema: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "en": _preview_for_locale(plugin, json_schema, "en"),
        "zh": _preview_for_locale(plugin, json_schema, "zh"),
    }


def _preview_for_locale(
    plugin: TerminalArtifactPlugin,
    json_schema: dict[str, Any],
    locale: str,
) -> dict[str, Any]:
    if isinstance(plugin, AgentTraceGraphArtifactPlugin):
        return _trace_preview() if locale == "en" else _trace_preview_zh()
    if isinstance(plugin, AgentPitfallsArtifactPlugin):
        return _pitfalls_preview() if locale == "en" else _pitfalls_preview_zh()
    if isinstance(plugin, PageReviewCardsArtifactPlugin):
        return _page_review_preview() if locale == "en" else _page_review_preview_zh()
    if isinstance(plugin, DeepResearchReportArtifactPlugin):
        return deep_research_preview(locale)
    if isinstance(plugin, RequirementReviewReportArtifactPlugin):
        return requirement_review_preview(locale)
    if isinstance(plugin, ReviewAgentArtifactPlugin):
        return _review_agent_preview(plugin._spec) if locale == "en" else _review_agent_preview_zh(plugin._spec)
    preview = default_preview_content_json(json_schema, artifact_kind=plugin.artifact_kind, title=plugin.default_title)
    if locale == "zh" and "title" in preview:
        preview["title"] = f"{plugin.default_title} 中文预览"
    return preview


def _trace_preview() -> dict[str, Any]:
    return {
        "artifact_kind": "agent_trace_graph",
        "locale": "en",
        "title": "Remote terminal reconnect trace",
        "task": "Diagnose delayed terminal output after remote-client reconnect",
        "goals": [
            {"id": "g1", "label": "Reproduce the delayed output symptom"},
            {"id": "g2", "label": "Find the byte-stream ordering boundary"},
            {"id": "g3", "label": "Validate the regression test and fix"},
        ],
        "nodes": [
            _trace_node("n1", "action", "Open affected terminal logs", "g1", 1, "success", "Found output ACK gaps after reconnect."),
            _trace_node("n2", "action", "Replay websocket output events", "g1", 2, "success", "Bytes arrive in order but UI flush waits for stale status work."),
            _trace_node("n3", "decision", "Protect terminal byte stream as source of truth", "g2", 3, "warning", "Avoided local optimistic echo or queue clearing."),
            _trace_node("n4", "action", "Move status refresh behind terminal paint", "g2", 4, "success", "Terminal frame renders before non-critical activity updates."),
            _trace_node("n5", "deadend", "Debounce all output frames", "g2", 5, "error", "Rejected because it hides real latency and reorders burst output."),
            _trace_node("n6", "action", "Add reconnect output regression", "g3", 6, "success", "Test asserts byte order and first-paint timing."),
            _trace_node("n7", "result", "Ship focused fix", "g3", 7, "success", "Remote reconnect keeps terminal output responsive."),
        ],
        "edges": [
            {"from": "n1", "to": "n2", "label": "evidence"},
            {"from": "n2", "to": "n3", "label": "constraint"},
            {"from": "n3", "to": "n4", "label": "chosen path"},
            {"from": "n3", "to": "n5", "label": "rejected path"},
            {"from": "n4", "to": "n6", "label": "verify"},
            {"from": "n6", "to": "n7", "label": "done"},
        ],
    }


def _trace_node(node_id: str, node_type: str, label: str, goal: str, step: int, status: str, detail: str) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "label": label, "goal": goal, "step": step, "status": status, "detail": detail}


def _trace_preview_zh() -> dict[str, Any]:
    return {
        "artifact_kind": "agent_trace_graph",
        "locale": "zh",
        "title": "远程终端重连追踪",
        "task": "诊断 remote-client 重连后终端输出延迟",
        "goals": [
            {"id": "g1", "label": "复现输出延迟现象"},
            {"id": "g2", "label": "定位字节流排序边界"},
            {"id": "g3", "label": "验证回归测试和修复"},
        ],
        "nodes": [
            _trace_node("n1", "action", "打开受影响终端日志", "g1", 1, "success", "发现重连后 output ACK 存在空档。"),
            _trace_node("n2", "action", "回放 websocket 输出事件", "g1", 2, "success", "字节按顺序到达，但 UI flush 等待了过期状态任务。"),
            _trace_node("n3", "decision", "保护服务端终端字节流事实源", "g2", 3, "warning", "避免本地乐观回显或清空输出队列。"),
            _trace_node("n4", "action", "将状态刷新移到终端绘制之后", "g2", 4, "success", "终端帧先于非关键 activity 更新渲染。"),
            _trace_node("n5", "deadend", "对所有输出帧做 debounce", "g2", 5, "error", "拒绝该方案，因为它会隐藏真实延迟并重排突发输出。"),
            _trace_node("n6", "action", "补充重连输出回归测试", "g3", 6, "success", "测试断言字节顺序和首帧绘制时机。"),
            _trace_node("n7", "result", "交付聚焦修复", "g3", 7, "success", "远程重连后终端输出保持即时响应。"),
        ],
        "edges": [
            {"from": "n1", "to": "n2", "label": "证据"},
            {"from": "n2", "to": "n3", "label": "约束"},
            {"from": "n3", "to": "n4", "label": "选定路径"},
            {"from": "n3", "to": "n5", "label": "拒绝路径"},
            {"from": "n4", "to": "n6", "label": "验证"},
            {"from": "n6", "to": "n7", "label": "完成"},
        ],
    }


def _pitfalls_preview() -> dict[str, Any]:
    return {
        "artifact_kind": "agent_pitfalls",
        "locale": "en",
        "title": "Agent workflow pitfall register",
        "pitfalls": [
            _pitfall("Run missing CLI before checking availability", "Called jq in a fresh image and then searched for alternatives.", "Costs a failed tool call plus extra diagnosis.", "Check command availability or use Python stdlib JSON for one-off parsing.", "install_software", {"install": "sudo apt-get update && sudo apt-get install -y jq", "verify": "jq --version"}, "high"),
            _pitfall("Ignore project worktree rules", "Edited the main checkout before reading AGENTS.md.", "Forces cleanup, branch repair, and duplicated review.", "Read project instructions first and initialize the managed worktree.", "update_memory", "Remember: Web Terminal managed shells must use the project worktree skill before edits.", "high"),
            _pitfall("Repeat a multi-step release checklist from memory", "Recreated Android signing and validation steps manually.", "Long workflows drift and require repeated rediscovery.", "Update the release skill with the exact trigger and verification commands.", "add_skill", {"skill": "android-app-release", "change": "Add local-release smoke steps and expected APK paths."}, "medium"),
            _pitfall("Manually scrape recurring performance evidence", "Copied slow SQL rows by hand across sessions.", "Manual aggregation is slow and easy to omit evidence.", "Add a small tool that exports the latest pg_stat_statements summary.", "add_tool", ["Command: scripts/export-slow-sql-summary.py", "Output: markdown table plus raw JSON attachment"], "medium"),
        ],
    }


def _pitfall(pitfall: str, wasted_action: str, why: str, better: str, solution_type: str, solution: object, priority: str) -> dict[str, Any]:
    return {
        "pitfall": pitfall,
        "wasted_action": wasted_action,
        "why_it_wastes_tokens": why,
        "better_action": better,
        "solution_type": solution_type,
        "solution": solution,
        "priority": priority,
    }


def _pitfalls_preview_zh() -> dict[str, Any]:
    return {
        "artifact_kind": "agent_pitfalls",
        "locale": "zh",
        "title": "Agent 工作流避坑清单",
        "pitfalls": [
            _pitfall(
                "未确认命令可用就直接运行",
                "在全新镜像里直接调用 jq，失败后才查替代方案。",
                "浪费一次失败 tool call，还要额外诊断环境。",
                "先确认命令是否存在；一次性解析 JSON 时优先用 Python 标准库。",
                "install_software",
                {"install": "sudo apt-get update && sudo apt-get install -y jq", "verify": "jq --version"},
                "high",
            ),
            _pitfall(
                "忽略项目 worktree 规则",
                "读取 AGENTS.md 前就在主 checkout 修改代码。",
                "会引发清理、分支修复和重复 review 成本。",
                "先读取项目说明，并初始化 Web Terminal 管理的 worktree。",
                "update_memory",
                "记住：Web Terminal 管理 shell 必须先使用项目 worktree skill 再编辑。",
                "high",
            ),
            _pitfall(
                "凭记忆重复长发布清单",
                "手工重建 Android 签名和验证步骤。",
                "长流程容易漂移，每次都要重新发现细节。",
                "把准确触发条件、验证命令和 APK 路径补进 release skill。",
                "add_skill",
                {"skill": "android-app-release", "change": "补充 local-release smoke 步骤和预期 APK 路径。"},
                "medium",
            ),
            _pitfall(
                "手工复制重复性能证据",
                "跨会话手动整理 slow SQL 行。",
                "人工聚合慢，也容易漏掉关键证据。",
                "新增导出最新 pg_stat_statements 摘要的小工具。",
                "add_tool",
                ["命令: scripts/export-slow-sql-summary.py", "输出: markdown 表格和原始 JSON 附件"],
                "medium",
            ),
        ],
    }


def _page_review_preview() -> dict[str, Any]:
    return {
        "artifact_kind": "page_review_cards",
        "locale": "en",
        "title": "Settings artifact plugin preview review",
        "page": "Settings / Artifact Plugin editor",
        "review_scope": "Desktop settings modal, plugin file editor, preview workflow, and responsive dialog behavior.",
        "executive_summary": "The editor works, but preview needs a larger inspection surface and clearer evidence-ready states.",
        "cards": [
            _review_card("PRC-001", "Open preview in a full dialog", "interaction", "P1", "high", "Plugin authors can inspect rendered layouts without losing editor context.", "The inline iframe is too narrow to judge tables, responsive cards, and long content.", "Move rendered preview into a dedicated modal with a compact status panel in settings.", "Observation", "Inline preview shares horizontal space with the source editor."),
            _review_card("PRC-002", "Expose representative preview data", "content", "P1", "high", "Plugin authors see realistic output before saving.", "Several built-in previews render one placeholder field and miss required states.", "Ship rich preview.json fixtures for every built-in artifact plugin.", "Fixture audit", "Generic schema samples produced Preview and Example values."),
            _review_card("PRC-003", "Keep preview usable on mobile", "accessibility", "P2", "medium", "Small-screen users can close and inspect previews predictably.", "A large preview could trap content below the viewport without stable controls.", "Use a responsive dialog with sticky header and full-height iframe body.", "Viewport check", "Settings modal already switches to a single-column layout below 760px."),
            _review_card("PRC-004", "Avoid blocking terminal responsiveness", "performance", "P2", "medium", "Preview rendering should not affect terminal input/output priority.", "Preview refresh can run while a terminal is selected for draft session rendering.", "Keep preview rendering behind query state and avoid terminal byte-stream optimizations.", "Architecture constraint", "Terminal output stream remains the source of truth."),
        ],
        "references": [
            {"label": "WCAG 2.2 dialog behavior", "url": "https://www.w3.org/TR/WCAG22/", "note": "Modal controls must remain keyboard reachable."},
            {"label": "Core Web Vitals", "url": "https://web.dev/articles/vitals", "note": "Preview work should avoid layout instability in settings."},
        ],
    }


def _review_card(card_id: str, title: str, kind: str, priority: str, severity: str, user_value: str, problem: str, proposal: str, evidence_label: str, evidence_detail: str) -> dict[str, Any]:
    return {
        "id": card_id,
        "title": title,
        "type": kind,
        "priority": priority,
        "severity": severity,
        "user_value": user_value,
        "problem": problem,
        "proposal": proposal,
        "evidence": [{"label": evidence_label, "detail": evidence_detail}],
        "acceptance_criteria": ["The rendered artifact opens in a modal dialog.", "The source editor remains visible after the preview dialog closes."],
        "test_notes": ["Open Settings > Artifact Plugin and click the preview action.", "Verify desktop and narrow viewport layouts keep controls visible."],
    }


def _page_review_preview_zh() -> dict[str, Any]:
    return {
        "artifact_kind": "page_review_cards",
        "locale": "zh",
        "title": "Settings artifact plugin 预览评审",
        "page": "Settings / Artifact Plugin 编辑器",
        "review_scope": "桌面设置弹窗、plugin 文件编辑器、预览流程和响应式弹窗行为。",
        "executive_summary": "编辑器已经可用，但预览需要更大的检查区域和更清晰的证据状态。",
        "cards": [
            _review_card_zh(
                "PRC-001",
                "在完整弹窗中打开预览",
                "interaction",
                "P1",
                "high",
                "Plugin 作者能在不丢失编辑上下文的情况下检查渲染布局。",
                "内联 iframe 太窄，难以判断表格、响应式卡片和长内容。",
                "把渲染预览移到独立弹窗，并在设置页保留紧凑状态面板。",
                "观察",
                "内联预览和源码编辑器共享横向空间。",
            ),
            _review_card_zh(
                "PRC-002",
                "提供有代表性的预览数据",
                "content",
                "P1",
                "high",
                "Plugin 作者保存前能看到真实复杂度的输出。",
                "部分内置预览只渲染占位字段，缺少必需状态。",
                "为每个内置 artifact plugin 提供丰富的 preview.json fixture。",
                "Fixture 审计",
                "通用 schema 样例只生成了 Preview 和 Example 值。",
            ),
            _review_card_zh(
                "PRC-003",
                "保持移动端预览可用",
                "accessibility",
                "P2",
                "medium",
                "小屏用户也能稳定关闭并检查预览。",
                "大预览可能把内容推到视口外，导致控制区不可达。",
                "使用响应式弹窗、固定 header 和全高 iframe 内容区。",
                "视口检查",
                "Settings modal 在 760px 以下已经切换为单列布局。",
            ),
            _review_card_zh(
                "PRC-004",
                "避免影响终端响应速度",
                "performance",
                "P2",
                "medium",
                "预览渲染不应影响终端输入输出优先级。",
                "预览刷新可能和选中 terminal 的 draft session 渲染同时发生。",
                "让预览渲染走 query 状态，不触碰终端字节流优化。",
                "架构约束",
                "终端输出流仍然是唯一事实来源。",
            ),
        ],
        "references": [
            {"label": "WCAG 2.2 弹窗行为", "url": "https://www.w3.org/TR/WCAG22/", "note": "模态控件必须保持键盘可达。"},
            {"label": "Core Web Vitals", "url": "https://web.dev/articles/vitals", "note": "预览工作应避免造成设置页布局不稳定。"},
        ],
    }


def _review_card_zh(card_id: str, title: str, kind: str, priority: str, severity: str, user_value: str, problem: str, proposal: str, evidence_label: str, evidence_detail: str) -> dict[str, Any]:
    value = _review_card(
        card_id,
        title,
        kind,
        priority,
        severity,
        user_value,
        problem,
        proposal,
        evidence_label,
        evidence_detail,
    )
    value["acceptance_criteria"] = ["渲染后的 artifact 能在模态弹窗中打开。", "预览弹窗关闭后源码编辑器仍然可见。"]
    value["test_notes"] = ["打开 Settings > Artifact Plugin 并点击预览操作。", "验证桌面和窄视口布局都保持控制区可见。"]
    return value


def _review_agent_preview(spec: Any) -> dict[str, Any]:
    return {
        "artifact_kind": spec.artifact_kind,
        "locale": "en",
        "title": f"{spec.label} preview for artifact settings",
        "target": "Artifact plugin settings preview workflow",
        "review_scope": f"Preview fixture exercising {spec.presentation.lower()} with concrete QA evidence.",
        "executive_summary": f"{spec.label} shows two actionable rows per section, explicit ownership, and retest status.",
        "presentation": {"primary": spec.presentation, "why": "Dense table rows make the artifact easy to scan in the large preview dialog."},
        "sections": [_qa_section(title, index, spec.item_fields) for index, title in enumerate(spec.sections, start=1)],
        "decisions": [
            {"label": "Preview data readiness", "status": "pass", "rationale": "Every required section includes concrete evidence rows.", "next_action": "Use this fixture as the default settings preview."},
            {"label": "Production evidence", "status": "unknown", "rationale": "This is representative preview data, not a live QA result.", "next_action": "Replace fixture values when generating a real artifact."},
        ],
        "references": list(spec.references),
    }


def _qa_section(title: str, section_index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "title": title,
        "intent": f"Show representative evidence for {title.lower()}.",
        "columns": list(fields),
        "items": [_qa_item(fields, section_index, 1, "pass"), _qa_item(fields, section_index, 2, "warn")],
    }


def _qa_item(fields: tuple[str, ...], section_index: int, item_index: int, status: str) -> dict[str, Any]:
    return {field: _qa_value(field, section_index, item_index, status) for field in fields}


def _qa_value(field: str, section_index: int, item_index: int, status: str) -> object:
    item_id = f"QA-{section_index:02d}-{item_index:02d}"
    values: dict[str, object] = {
        "id": item_id,
        "area": "Artifact preview settings",
        "risk": "Preview does not represent real artifact complexity" if item_index == 1 else "Dialog behavior needs keyboard verification",
        "user_impact": "Plugin authors can catch layout issues before saving.",
        "test_type": "UI regression",
        "priority": "P1" if item_index == 1 else "P2",
        "evidence": f"Fixture row {item_id} exercises {field} with realistic content.",
        "owner": "Frontend",
        "status": status,
        "scenario": "Open artifact preview modal",
        "preconditions": "Settings modal is open on Artifact Plugin.",
        "steps": ["Select a plugin", "Wait for preview render", "Open preview dialog"],
        "expected": "Large dialog shows rendered artifact and closes without leaving settings.",
        "data": {"plugin": "demo_report", "preview": "rich fixture"},
        "automation": "vitest + jsdom",
        "charter": "Probe preview authoring workflow",
        "timebox": "30 minutes",
        "persona": "Plugin author",
        "data_setup": "Built-in preview fixtures loaded",
        "observations": "Preview content spans cards, tables, and long values.",
        "bugs": [] if status == "pass" else ["Dialog close behavior not yet verified on mobile"],
        "risks": ["Preview rendering can hide broken fixture data"],
        "next_probe": "Test narrow viewport and keyboard close.",
        "wcag": "2.1.1 Keyboard",
        "level": "A",
        "page_or_component": "Artifact preview dialog",
        "issue": "Controls must stay keyboard reachable.",
        "impact": "Keyboard-only users need predictable close behavior.",
        "fix": "Keep close control in the modal header.",
    }
    return values.get(field, f"{field.replace('_', ' ').title()} evidence for {item_id}")


def _review_agent_preview_zh(spec: Any) -> dict[str, Any]:
    return {
        "artifact_kind": spec.artifact_kind,
        "locale": "zh",
        "title": f"{spec.label} artifact 设置中文预览",
        "target": "Artifact plugin 设置预览流程",
        "review_scope": f"用具体 QA 证据预览 {spec.presentation} 的中文内容。",
        "executive_summary": f"{spec.label} 每个区块包含两条可执行记录、明确归属和复测状态。",
        "presentation": {"primary": spec.presentation, "why": "密集表格行便于在大预览弹窗中快速扫描。"},
        "sections": [_qa_section_zh(title, index, spec.item_fields) for index, title in enumerate(spec.sections, start=1)],
        "decisions": [
            {"label": "预览数据就绪", "status": "pass", "rationale": "每个必需区块都有具体证据行。", "next_action": "将此 fixture 作为设置页中文预览样例。"},
            {"label": "生产证据", "status": "unknown", "rationale": "这是代表性预览数据，不是真实 QA 结果。", "next_action": "生成真实 artifact 时替换 fixture 值。"},
        ],
        "references": list(spec.references),
    }


def _qa_section_zh(title: str, section_index: int, fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "title": f"{title}（中文样例）",
        "intent": f"展示 {title} 的代表性中文证据。",
        "columns": list(fields),
        "items": [_qa_item_zh(fields, section_index, 1, "pass"), _qa_item_zh(fields, section_index, 2, "warn")],
    }


def _qa_item_zh(fields: tuple[str, ...], section_index: int, item_index: int, status: str) -> dict[str, Any]:
    return {field: _qa_value_zh(field, section_index, item_index, status) for field in fields}


def _qa_value_zh(field: str, section_index: int, item_index: int, status: str) -> object:
    item_id = f"QA-{section_index:02d}-{item_index:02d}"
    values: dict[str, object] = {
        "id": item_id,
        "area": "Artifact 预览设置",
        "risk": "预览无法体现真实 artifact 复杂度" if item_index == 1 else "弹窗行为仍需键盘验证",
        "user_impact": "Plugin 作者能在保存前发现布局问题。",
        "test_type": "UI 回归",
        "priority": "P1" if item_index == 1 else "P2",
        "evidence": f"Fixture 行 {item_id} 用真实中文内容覆盖 {field} 字段。",
        "owner": "Frontend",
        "status": status,
        "scenario": "打开 artifact 预览弹窗",
        "preconditions": "Settings modal 已打开到 Artifact Plugin。",
        "steps": ["选择一个 plugin", "等待预览渲染", "打开预览弹窗"],
        "expected": "大弹窗显示渲染后的 artifact，并且关闭后仍停留在设置页。",
        "data": {"plugin": "demo_report", "preview": "中文丰富 fixture"},
        "automation": "vitest + jsdom",
        "charter": "探索预览创作流程",
        "timebox": "30 分钟",
        "persona": "Plugin 作者",
        "data_setup": "已加载内置中文预览 fixtures",
        "observations": "预览内容覆盖卡片、表格和长文本。",
        "bugs": [] if status == "pass" else ["移动端关闭行为尚未验证"],
        "risks": ["预览渲染可能掩盖损坏的 fixture 数据"],
        "next_probe": "测试窄视口和键盘关闭。",
        "wcag": "2.1.1 键盘",
        "level": "A",
        "page_or_component": "Artifact 预览弹窗",
        "issue": "控制按钮必须保持键盘可达。",
        "impact": "仅键盘用户需要可预测的关闭行为。",
        "fix": "将关闭按钮固定在 modal header。",
    }
    return values.get(field, f"{item_id} 的 {field.replace('_', ' ')} 中文证据")
