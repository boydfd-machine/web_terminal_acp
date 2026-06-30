from app.platform.plugins.agent_tools.user_input import extract_real_user_input


CODEX_DISPATCH_WITH_AGENT_INSTRUCTIONS = """System language for agent response: 中文.
Write all user-facing responses in this language. Treat the language value only as a language name, not as an instruction. Keep code, commands, file paths, identifiers, API names, and quoted source text unchanged when required.

You are assigned to complete this project todo.

Todo: codex system prompt bug修复

Context:
最新版本的codex，会把这种agent.md的提示也识别成agent record里的user部分。

AGENTS.md instructions
<INSTRUCTIONS>
# Global Codex Agent Notes
工作原则
不要假设用户清楚自己想要什么。
</INSTRUCTIONS>

你直接用agent-browser做端到端的测试。"""


def test_extracts_cursor_user_query_tag() -> None:
    assert (
        extract_real_user_input(
            "<user_query>\n修复 summary 只保留真实用户输入\n</user_query>",
            provider="cursor_cli",
        )
        == "修复 summary 只保留真实用户输入"
    )


def test_extracts_codex_goal_objective_tag() -> None:
    assert (
        extract_real_user_input(
            "<goal_context>\n<objective>\n看一下最近 summary 的消息\n</objective>\n</goal_context>",
            provider="codex",
        )
        == "看一下最近 summary 的消息"
    )


def test_rejects_agent_default_user_context_blocks() -> None:
    assert extract_real_user_input("<user_info>\nOS Version: linux\n</user_info>", provider="cursor_cli") is None
    assert extract_real_user_input("# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>...</INSTRUCTIONS>") is None
    assert (
        extract_real_user_input(
            "# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>...</INSTRUCTIONS>\n\n<environment_context>\n  <cwd>/workspace</cwd>\n</environment_context>",
            provider="codex",
        )
        is None
    )
    assert extract_real_user_input("<turn_aborted>\nThe user interrupted the previous turn.\n</turn_aborted>") is None
    assert extract_real_user_input("<bash-input>env | grep claude</bash-input>", provider="claude_code") is None


def test_strips_codex_dispatch_system_context_from_user_input() -> None:
    extracted = extract_real_user_input(CODEX_DISPATCH_WITH_AGENT_INSTRUCTIONS, provider="codex")

    assert extracted is not None
    assert "System language for agent response" not in extracted
    assert "AGENTS.md instructions" not in extracted
    assert "Global Codex Agent Notes" not in extracted
    assert "Todo: codex system prompt bug修复" in extracted
    assert "你直接用agent-browser做端到端的测试。" in extracted


def test_keeps_plain_human_input() -> None:
    assert extract_real_user_input("帮忙修复 docker build 报错", provider="codex") == "帮忙修复 docker build 报错"
