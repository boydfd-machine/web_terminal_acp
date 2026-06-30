from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.mcp_acp.application.service import McpAcpService
from app.contexts.terminal_runtime.application.agent_prompt_input import (
    bracketed_paste_bytes,
    command_bytes_for_agent_prompt,
    terminal_prompt_bytes,
)


def test_bracketed_paste_bytes_preserves_newlines() -> None:
    """Test that bracketed paste preserves newlines in multiline prompts."""
    multiline_prompt = "Line 1\nLine 2\nLine 3"
    result = bracketed_paste_bytes(multiline_prompt)
    # Should preserve \n, not convert to \r
    assert result == b"\x1b[200~Line 1\nLine 2\nLine 3\x1b[201~"

    # Test with \r\n normalization
    windows_prompt = "Line 1\r\nLine 2\r\nLine 3"
    result = bracketed_paste_bytes(windows_prompt)
    assert result == b"\x1b[200~Line 1\nLine 2\nLine 3\x1b[201~"

    # Test with mixed line endings
    mixed_prompt = "Line 1\r\nLine 2\nLine 3\rLine 4"
    result = bracketed_paste_bytes(mixed_prompt)
    assert result == b"\x1b[200~Line 1\nLine 2\nLine 3\nLine 4\x1b[201~"


def test_command_bytes_for_codex_uses_bracketed_paste() -> None:
    """Test that codex uses bracketed paste for submit mode."""
    multiline_prompt = "Todo: Fix bug\n\nContext:\nDetails here"
    result = command_bytes_for_agent_prompt(
        "codex",
        multiline_prompt,
        submit_prompt=True,
        bracketed_paste_for_submit_providers=frozenset({"codex"}),
    )
    # Should use bracketed paste + composer submit
    assert result.startswith(b"\x1b[200~")
    assert result.endswith(b"\x1b[201~\x1b[13u")
    assert b"Todo: Fix bug\n\nContext:\nDetails here" in result


def test_command_bytes_for_claude_code_uses_bracketed_paste_and_enter_submit() -> None:
    multiline_prompt = "Todo: Fix bug\n\nContext:\nDetails here"
    result = command_bytes_for_agent_prompt(
        "claude",
        multiline_prompt,
        submit_prompt=True,
        bracketed_paste_for_submit_providers=frozenset({"codex", "claude_code"}),
    )
    assert result.startswith(b"\x1b[200~")
    assert result.endswith(b"\x1b[201~\n")
    assert b"Todo: Fix bug\n\nContext:\nDetails here" in result


def test_command_bytes_for_antigravity_uses_bracketed_paste_and_composer_submit() -> None:
    multiline_prompt = "Todo: Fix bug\n\nContext:\nDetails here"
    result = command_bytes_for_agent_prompt(
        "agy-p",
        multiline_prompt,
        submit_prompt=True,
        bracketed_paste_for_submit_providers=frozenset({"antigravity_cli"}),
    )
    assert result == b"\x1b[200~Todo: Fix bug\n\nContext:\nDetails here\x1b[201~\x1b[13u"


def test_command_bytes_for_cursor_uses_bracketed_paste_and_enter_submit() -> None:
    multiline_prompt = "Todo: Fix bug\n\nContext:\nDetails here"
    result = command_bytes_for_agent_prompt(
        "agent",
        multiline_prompt,
        submit_prompt=True,
        bracketed_paste_for_submit_providers=frozenset({"cursor_cli"}),
    )
    assert result == b"\x1b[200~Todo: Fix bug\n\nContext:\nDetails here\x1b[201~\n"


def test_terminal_prompt_bytes_uses_cursor_composer_submit() -> None:
    assert terminal_prompt_bytes("agent", "todo prompt") == b"todo prompt\x1b[13u"
    assert terminal_prompt_bytes("cursor-agent", "todo prompt") == b"todo prompt\x1b[13u"
    assert terminal_prompt_bytes("codex", "todo prompt") == b"todo prompt\x1b[13u"
    assert terminal_prompt_bytes("claude", "todo prompt") == b"todo prompt\n"
    assert terminal_prompt_bytes("agy-p", "todo prompt") == b"todo prompt\x1b[13u"
    assert terminal_prompt_bytes("/bin/bash", "todo prompt") == b"todo prompt\n"


@pytest.mark.asyncio
async def test_mcp_initial_prompt_uses_cursor_composer_submit() -> None:
    client_id = uuid4()
    window_id = uuid4()
    sent: list[dict[str, object]] = []
    service = McpAcpService(
        session=object(),
        app_state=object(),
        tmux_manager=object(),
        session_factory=lambda: None,
    )

    async def fake_wait_for_runtime_ready(_client_id, _window_id):
        return SimpleNamespace(id=window_id, shell_command="agent")

    async def fake_require_client(_client_id, *, owner_user_id=None):
        return SimpleNamespace(id=client_id)

    class FakeTerminalRuntime:
        async def send_input(self, **kwargs):
            sent.append(kwargs)

    service._wait_for_runtime_ready = fake_wait_for_runtime_ready
    service._require_client = fake_require_client
    service._terminal_runtime = lambda: FakeTerminalRuntime()

    await service._send_prompt_after_ready(
        client_id,
        SimpleNamespace(id=window_id),
        "todo prompt",
        owner_user_id=None,
    )

    assert sent[0]["data"] == b"todo prompt\x1b[13u"
