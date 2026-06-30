from __future__ import annotations

from html import escape
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .types import TerminalArtifactRender

SOLUTION_TYPES = ("install_software", "update_memory", "add_skill", "add_tool")
SOLUTION_LABELS = {
    "install_software": "Install Software",
    "update_memory": "Update Memory",
    "add_skill": "Add / Update Skill",
    "add_tool": "Add Tool",
}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PITFALL_CLASSIFICATION_GUIDANCE = (
    " solution_type 必须按根因分类，不要按表面动作分类。"
    " install_software 只用于缺少可安装的系统工具、语言依赖、本地依赖树、浏览器或驱动，"
    " 且安装后能稳定减少重复失败；solution 必须写安装和验证命令。"
    " 示例：缺少 jq/rg/tree；fresh frontend worktree 缺 node_modules 时先 npm ci --ignore-scripts；"
    " Playwright 浏览器缺失时安装 browsers；需要 Electron/native/release artifact 时才使用完整 npm ci。"
    " update_memory 用于单步习惯或项目约定错误，更新一条记忆或 AGENTS 说明即可避免；不要用来安装包。"
    " 示例：先猜 npm script 名而不是读取 package.json；在 Web Terminal 主 checkout 改代码而不走 worktree/merge；"
    " 每次 git status 都查看 ignored 的 dist/node_modules。"
    " add_skill 用于高频、多步骤、含判断分支的流程，需要创建或更新 SKILL.md/脚本固化；"
    " 如果已有相关 skill，solution 要写明更新哪个 skill、补什么触发条件或步骤。"
    " 示例：Android release 打包签名验证流程；慢 SQL 排查和记录流程；"
    " agent pitfalls 分类规则反复生成错误时更新 agent-pitfalls 相关 skill/prompt。"
    " add_tool 只用于现有 shell 命令、软件、记忆和 skill 都不能稳定省 token，需要新增自动化工具或 API 集成。"
    " 分类例外：检查已有依赖、读取 package.json、选择更小安装命令通常只是 better_action 或 update_memory；"
    " 只有根因确实是缺本地依赖树或工具时才归 install_software。"
)


class AgentPitfallsArtifactPlugin:
    artifact_kind = "agent_pitfalls"
    label = "Agent Pitfalls"
    default_title = "Agent token-saving pitfalls"

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        extra = f" 用户补充要求: {_single_line(user_prompt)}" if user_prompt else ""
        output_instruction = ""
        if output_path:
            temp_path = f"{output_path}.tmp"
            output_instruction = (
                f" 不要把 JSON 输出到聊天窗口；必须把最终 JSON 一次性写入文件 {output_path}。"
                f" 推荐先写临时文件 {temp_path}，校验 JSON 后用 mv {temp_path} {output_path} 原子替换。"
                " 写入后只回复一句 artifact JSON saved，不要附带 JSON 内容。"
            )
        prompt = (
            "生成 agent 通用避坑 artifact。只记录跨任务可复用、会浪费 token/tool call/等待时间的坑。"
            " 不要复盘当前任务细节，除非它能作为通用坑的证据。"
            f" 可参考当前已经恢复/复制的 session 上下文和 terminal “{source_title}”，"
            " 但 artifact 必须面向以后任何任务都可能再踩的模式。"
            " 每条坑必须给出更省 token 的替代动作，以及解决方案类型。"
            " 解决方案优先级固定为：install_software > update_memory > add_skill > add_tool。"
            f"{PITFALL_CLASSIFICATION_GUIDANCE}"
            " 只输出合法 JSON，不要输出 Markdown fenced code，不要渲染 HTML，不要截图。"
            " JSON schema: {\"artifact_kind\":\"agent_pitfalls\",\"title\":\"Agent token-saving pitfalls\","
            "\"pitfalls\":[{\"pitfall\":\"...\",\"wasted_action\":\"...\","
            "\"why_it_wastes_tokens\":\"...\",\"better_action\":\"...\","
            "\"solution_type\":\"install_software|update_memory|add_skill|add_tool\","
            "\"solution\":{},\"priority\":\"high|medium|low\"}]}"
            " solution 可以是对象、字符串或字符串数组，但必须具体可执行。"
            " priority 按省 token 收益排序；不要输出空 pitfalls，若没有足够证据也要记录可从上下文确认的通用坑。"
            f"{output_instruction}"
            " 输出完成后停止。"
            f"{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        for candidate in _iter_json_objects(output):
            normalized = _normalize_agent_pitfalls_json(candidate)
            if normalized is not None:
                return normalized
        for candidate in _iter_wrapped_json_objects(output):
            normalized = _normalize_agent_pitfalls_json(candidate)
            if normalized is not None:
                return normalized
        raise ValueError("agent pitfalls JSON was not found in terminal output")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = _normalize_agent_pitfalls_json(content_json)
        if normalized is None:
            raise ValueError("invalid agent pitfalls JSON")
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=_render_agent_pitfalls_html(normalized),
            metadata_json={"renderer": "agent-pitfalls"},
        )


def _normalize_agent_pitfalls_json(value: dict[str, Any]) -> dict[str, Any] | None:
    pitfalls = value.get("pitfalls")
    if not isinstance(pitfalls, list):
        return None
    normalized_pitfalls = [
        normalized
        for item in pitfalls
        if isinstance(item, dict) and (normalized := _normalize_pitfall(item)) is not None
    ]
    if not normalized_pitfalls:
        return None
    normalized_pitfalls.sort(key=_pitfall_sort_key)
    title = value.get("title")
    return {
        "artifact_kind": "agent_pitfalls",
        "title": title if isinstance(title, str) and title.strip() else "Agent token-saving pitfalls",
        "pitfalls": normalized_pitfalls,
    }


def _normalize_pitfall(value: dict[str, Any]) -> dict[str, Any] | None:
    solution_type = _text(value.get("solution_type")).lower()
    if solution_type not in SOLUTION_TYPES:
        return None
    normalized = {
        "pitfall": _text(value.get("pitfall")),
        "wasted_action": _text(value.get("wasted_action")),
        "why_it_wastes_tokens": _text(value.get("why_it_wastes_tokens")),
        "better_action": _text(value.get("better_action")),
        "solution_type": solution_type,
        "solution": value.get("solution") if value.get("solution") is not None else "",
        "priority": _priority(value.get("priority")),
    }
    required = ("pitfall", "wasted_action", "why_it_wastes_tokens", "better_action")
    if any(not normalized[field] for field in required):
        return None
    return normalized


def _pitfall_sort_key(value: dict[str, Any]) -> tuple[int, int, str]:
    return (
        PRIORITY_ORDER.get(value["priority"], len(PRIORITY_ORDER)),
        SOLUTION_TYPES.index(value["solution_type"]),
        value["pitfall"].lower(),
    )


def _priority(value: object) -> str:
    priority = _text(value).lower()
    return priority if priority in PRIORITY_ORDER else "medium"


def _text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _render_agent_pitfalls_html(content: dict[str, Any]) -> str:
    pitfalls = content["pitfalls"]
    sections = "\n".join(
        _render_solution_section(solution_type, pitfalls)
        for solution_type in SOLUTION_TYPES
        if any(item["solution_type"] == solution_type for item in pitfalls)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(_text(content.get("title")))}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #d1d5db;
      --install: #047857;
      --memory: #2563eb;
      --skill: #7c3aed;
      --tool: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.55 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 20px; }}
    h1 {{ margin: 0; font-size: 26px; line-height: 1.2; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .summary {{ color: var(--muted); margin-top: 6px; }}
    .count {{ border: 1px solid var(--border); border-radius: 999px; padding: 6px 12px; background: var(--panel); white-space: nowrap; }}
    .section {{ margin-top: 18px; }}
    .grid {{ display: grid; gap: 12px; }}
    .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 10px; }}
    .title {{ font-weight: 750; font-size: 16px; }}
    .badges {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
    .badge {{ border-radius: 999px; color: #fff; padding: 3px 8px; font-size: 11px; font-weight: 750; text-transform: uppercase; }}
    .priority {{ background: #374151; }}
    .install_software {{ background: var(--install); }}
    .update_memory {{ background: var(--memory); }}
    .add_skill {{ background: var(--skill); }}
    .add_tool {{ background: var(--tool); }}
    dl {{ display: grid; gap: 8px; margin: 0; }}
    dt {{ color: var(--muted); font-size: 12px; font-weight: 750; text-transform: uppercase; }}
    dd {{ margin: 0; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      padding: 10px;
      font-size: 12px;
    }}
    @media (max-width: 720px) {{
      main {{ padding: 18px; }}
      header, .card-head {{ display: grid; }}
      .badges {{ justify-content: flex-start; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{escape(_text(content.get("title")))}</h1>
        <div class="summary">Reusable pitfalls that waste agent tokens, tool calls, or waiting time.</div>
      </div>
      <div class="count">{len(pitfalls)} pitfalls</div>
    </header>
    {sections}
  </main>
</body>
</html>"""


def _render_solution_section(solution_type: str, pitfalls: list[dict[str, Any]]) -> str:
    items = [item for item in pitfalls if item["solution_type"] == solution_type]
    cards = "\n".join(_render_pitfall_card(item) for item in items)
    return f"""<section class="section">
  <h2>{escape(SOLUTION_LABELS[solution_type])}</h2>
  <div class="grid">
    {cards}
  </div>
</section>"""


def _render_pitfall_card(item: dict[str, Any]) -> str:
    solution_type = item["solution_type"]
    return f"""<article class="card">
  <div class="card-head">
    <div class="title">{escape(item["pitfall"])}</div>
    <div class="badges">
      <span class="badge priority">{escape(item["priority"])}</span>
      <span class="badge {escape(solution_type)}">{escape(SOLUTION_LABELS[solution_type])}</span>
    </div>
  </div>
  <dl>
    <dt>Wasted Action</dt>
    <dd>{escape(item["wasted_action"])}</dd>
    <dt>Why It Wastes Tokens</dt>
    <dd>{escape(item["why_it_wastes_tokens"])}</dd>
    <dt>Better Action</dt>
    <dd>{escape(item["better_action"])}</dd>
    <dt>Solution</dt>
    <dd>{_render_solution(item["solution"])}</dd>
  </dl>
</article>"""


def _render_solution(value: object) -> str:
    if isinstance(value, dict):
        return "<pre>" + escape(_format_solution_dict(value)) + "</pre>"
    if isinstance(value, list):
        lines = [_text(item) for item in value if _text(item)]
        return "<pre>" + escape("\n".join(lines)) + "</pre>"
    return escape(_text(value))


def _format_solution_dict(value: dict[object, object]) -> str:
    lines: list[str] = []
    for key, item in value.items():
        if isinstance(item, list):
            detail = "\n  " + "\n  ".join(_text(entry) for entry in item)
        else:
            detail = _text(item)
        lines.append(f"{_text(key)}: {detail}")
    return "\n".join(lines)
