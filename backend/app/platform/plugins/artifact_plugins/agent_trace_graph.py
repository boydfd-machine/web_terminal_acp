from __future__ import annotations

import json
import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from .types import TerminalArtifactRender

AGENT_TRACE_GRAPH_SKILL_PATH_HINTS = (
    "~/.claude/skills/agent-trace-graph/SKILL.md",
    "$CLAUDE_CONFIG_DIR/skills/agent-trace-graph/SKILL.md",
    "$CODEX_HOME/skills/agent-trace-graph/SKILL.md",
    "$CURSOR_AGENT_HOME/skills-cursor/agent-trace-graph/SKILL.md",
    "$WEB_TERMINAL_CLAUDE_CODE_HOME/skills/agent-trace-graph/SKILL.md",
    "$WEB_TERMINAL_CODEX_HOME/skills/agent-trace-graph/SKILL.md",
    "$WEB_TERMINAL_CURSOR_HOME/skills-cursor/agent-trace-graph/SKILL.md",
    "$WEB_TERMINAL_ANTIGRAVITY_HOME/skills/agent-trace-graph/SKILL.md",
)


class AgentTraceGraphArtifactPlugin:
    artifact_kind = "agent_trace_graph"
    label = "Agent Trace Graph"
    default_title = "Agent trace graph"

    def __init__(self, *, render_script: Path | None = None) -> None:
        self._render_script = render_script

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
            "请先读取并遵循 agent-trace-graph skill 的 SKILL.md 指令；"
            "如果当前 agent-client 没有自动加载该 skill，请优先尝试这些路径: "
            f"{', '.join(AGENT_TRACE_GRAPH_SKILL_PATH_HINTS)}。"
            " 基于当前已经恢复/复制的 session 上下文，"
            f"为 terminal “{source_title}” 的这次探索/执行过程生成 artifact JSON。"
            " 只输出一份合法 JSON，不要输出 Markdown fenced code，不要渲染 HTML，不要截图。"
            " JSON 必须包含 task、goals、nodes、edges，且 deadend 节点不能再有 tried/leads-to 出边。"
            " 不要在字符串字段里嵌入原始 JSON；如果要提到命令输出，用自然语言摘要或转义后的字符串。"
            f"{output_instruction}"
            " 输出完成后停止。"
            f"{extra}"
        )
        return _single_line(prompt)

    def parse_output(self, output: str) -> dict:
        for candidate in _iter_json_objects(output):
            if _is_agent_trace_graph_json(candidate):
                return candidate
        for candidate in _iter_wrapped_json_objects(output):
            if _is_agent_trace_graph_json(candidate):
                return candidate
        raise ValueError("agent trace graph JSON was not found in terminal output")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        if self._render_script is not None:
            html = _render_agent_trace_graph_html(content_json, self._render_script)
            return TerminalArtifactRender(
                content_json=content_json,
                display_html=html,
                metadata_json={
                    "renderer": "agent-trace-graph",
                    "render_script": str(self._render_script),
                },
            )
        return _agent_trace_template_plugin().render(content_json)


def _iter_json_objects(text: str):
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        brace = text.find("{", index)
        if brace == -1:
            return
        try:
            value, end = decoder.raw_decode(text[brace:])
        except json.JSONDecodeError:
            index = brace + 1
            continue
        if isinstance(value, dict):
            yield value
        index = brace + max(1, end)


def _iter_wrapped_json_objects(text: str):
    seen: set[str] = set()
    for block in (*_iter_braced_blocks(text), *_iter_loose_agent_trace_blocks(text)):
        if block in seen:
            continue
        seen.add(block)
        repaired = _repair_wrapped_json_strings(block)
        try:
            value = json.loads(repaired)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield value


def _iter_braced_blocks(text: str):
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            return
        depth = 0
        in_string = False
        escaped = False
        for offset in range(start, len(text)):
            char = text[offset]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : offset + 1]
                    index = offset + 1
                    break
        else:
            return


def _iter_loose_agent_trace_blocks(text: str):
    index = 0
    while index < len(text):
        start = text.find('{"task"', index)
        if start == -1:
            return
        depth = 0
        for offset in range(start, len(text)):
            char = text[offset]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : offset + 1]
                    index = offset + 1
                    break
        else:
            return


def _repair_wrapped_json_strings(text: str) -> str:
    output: list[str] = []
    stack: list[dict[str, str]] = []
    in_string = False
    escaped = False
    string_role = "value"
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                output.append(char)
                escaped = False
            elif char == "\\":
                output.append(char)
                escaped = True
            elif char == '"':
                if _quote_terminates_string(text, index, string_role):
                    output.append(char)
                    in_string = False
                    if string_role == "value":
                        _mark_current_value_complete(stack)
                else:
                    output.append('\\"')
            elif char in "\r\n":
                while index + 1 < len(text) and text[index + 1] in " \t\r\n":
                    index += 1
                if output and output[-1] not in {" ", "\t"}:
                    output.append(" ")
            else:
                output.append(char)
        else:
            output.append(char)
            if char == '"':
                in_string = True
                string_role = _next_string_role(stack)
            elif char == "{":
                stack.append({"kind": "object", "expect": "key"})
            elif char == "[":
                stack.append({"kind": "array", "expect": "value"})
            elif char == "}":
                if stack and stack[-1]["kind"] == "object":
                    stack.pop()
                    _mark_current_value_complete(stack)
            elif char == "]":
                if stack and stack[-1]["kind"] == "array":
                    stack.pop()
                    _mark_current_value_complete(stack)
            elif char == ":":
                if stack and stack[-1]["kind"] == "object":
                    stack[-1]["expect"] = "value"
            elif char == ",":
                if stack:
                    if stack[-1]["kind"] == "object":
                        stack[-1]["expect"] = "key"
                    elif stack[-1]["kind"] == "array":
                        stack[-1]["expect"] = "value"
        index += 1
    return "".join(output)


def _next_string_role(stack: list[dict[str, str]]) -> str:
    if stack and stack[-1]["kind"] == "object" and stack[-1]["expect"] == "key":
        return "key"
    return "value"


def _mark_current_value_complete(stack: list[dict[str, str]]) -> None:
    if not stack:
        return
    if stack[-1]["kind"] == "object" and stack[-1]["expect"] == "value":
        stack[-1]["expect"] = "after_value"
    elif stack[-1]["kind"] == "array" and stack[-1]["expect"] == "value":
        stack[-1]["expect"] = "after_value"


def _quote_terminates_string(text: str, index: int, role: str) -> bool:
    next_index = _skip_json_whitespace(text, index + 1)
    if next_index >= len(text):
        return True
    if role == "key":
        return text[next_index] == ":"
    return _value_string_has_valid_tail(text, next_index)


def _value_string_has_valid_tail(text: str, index: int) -> bool:
    char = text[index]
    if char == ",":
        return True
    if char not in "]}":
        return False
    while index < len(text):
        char = text[index]
        if char in " \t\r\n]}":
            index += 1
            continue
        return char == ","
    return True


def _skip_json_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _single_line(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _is_agent_trace_graph_json(value: dict[str, Any]) -> bool:
    goals = value.get("goals")
    nodes = value.get("nodes")
    edges = value.get("edges")
    return (
        isinstance(value.get("task"), str)
        and isinstance(goals, list)
        and isinstance(nodes, list)
        and isinstance(edges, list)
    )


def _render_agent_trace_graph_html(content_json: dict, render_script: Path) -> str:
    if not render_script.is_file():
        raise ValueError(f"agent trace graph renderer not found: {render_script}")
    with tempfile.TemporaryDirectory(prefix="web-terminal-artifact-") as temp_dir:
        temp_path = Path(temp_dir)
        json_path = temp_path / "artifact.json"
        html_path = temp_path / "artifact.html"
        json_path.write_text(
            json.dumps(content_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            ["python3", str(render_script), str(json_path), "-o", str(html_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "renderer failed"
            raise ValueError(detail[:2000])
        return html_path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _agent_trace_template_plugin():
    from .component_storage import components_from_parts
    from .template_plugin import TemplateTerminalArtifactPlugin
    from .trace_template_components import agent_trace_python_source, trace_html_template

    plugin = AgentTraceGraphArtifactPlugin(render_script=Path("__unused__"))
    with tempfile.TemporaryDirectory(prefix="agent-trace-template-") as temp_dir:
        components = components_from_parts(
            python_source=agent_trace_python_source(plugin),
            prompt_template=plugin.build_prompt(source_title="{{ source_title }}"),
            html_template=trace_html_template().strip() + "\n",
            json_schema=_agent_trace_json_schema(),
            preview_content_json={"task": "Preview", "goals": [], "nodes": [], "edges": []},
            root=Path(temp_dir),
        )
    return TemplateTerminalArtifactPlugin(components)


def _agent_trace_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["task", "goals", "nodes", "edges"],
        "properties": {
            "task": {"type": "string"},
            "goals": {"type": "array"},
            "nodes": {"type": "array"},
            "edges": {"type": "array"},
        },
        "additionalProperties": True,
    }
