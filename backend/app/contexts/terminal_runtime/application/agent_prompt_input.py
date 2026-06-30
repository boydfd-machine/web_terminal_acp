from __future__ import annotations

import re

from app.client_agent.agent_commands import agent_provider_from_command

AGENT_COMPOSER_SUBMIT_INPUT = b"\x1b[13u"
BRACKETED_PASTE_START = b"\x1b[200~"
BRACKETED_PASTE_END = b"\x1b[201~"
COMPOSER_SUBMIT_PROVIDERS = frozenset({"codex", "cursor_cli", "antigravity_cli"})
FOLLOWUP_COMPOSER_SUBMIT_PROVIDERS = frozenset({"codex"})
BRACKETED_PASTE_ENTER_SUBMIT_PROVIDERS = frozenset({"cursor_cli"})
MULTILINE_PROMPT_BRACKETED_PASTE_PROVIDERS = frozenset(
    {"codex", "claude_code", "cursor_cli", "antigravity_cli"}
)
ARTIFACT_PROMPT_BRACKETED_PASTE_PROVIDERS = frozenset({"claude_code", "cursor_cli", "antigravity_cli"})
AGENT_PROMPT_MARKERS_BY_PROVIDER = {
    "codex": ("›",),
    "claude_code": ("❯",),
    "cursor_cli": (">", "›", "❯", "`", "→"),
    "antigravity_cli": (">", "›", "❯", "`"),
}
GENERIC_AGENT_PROMPT_MARKERS = ("›", "❯", ">")
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def command_bytes_for_agent_prompt(
    shell_command: str | None,
    prompt: str,
    *,
    submit_prompt: bool = True,
    bracketed_paste_for_submit_providers: frozenset[str] = frozenset(),
    error_message: str = "prompt dispatch requires an interactive agent terminal",
) -> bytes:
    if shell_command and looks_like_agent_command(shell_command):
        provider = agent_provider_for_prompt(shell_command)
        if provider in bracketed_paste_for_submit_providers or not submit_prompt:
            data = bracketed_paste_bytes(prompt)
        else:
            data = prompt.encode("utf-8")
        if submit_prompt:
            data += agent_prompt_submit_bytes(
                shell_command,
                bracketed_paste_used=provider in bracketed_paste_for_submit_providers,
            )
        return data
    raise ValueError(error_message)


def terminal_prompt_bytes(shell_command: str | None, prompt: str) -> bytes:
    if shell_command and looks_like_agent_command(shell_command):
        return command_bytes_for_agent_prompt(shell_command, prompt)
    return prompt.encode("utf-8") + b"\n"


def bracketed_paste_bytes(prompt: str) -> bytes:
    normalized = prompt.replace("\r\n", "\n").replace("\r", "\n")
    return BRACKETED_PASTE_START + normalized.encode("utf-8") + BRACKETED_PASTE_END


def agent_prompt_submit_bytes(shell_command: str | None, *, bracketed_paste_used: bool = False) -> bytes:
    provider = agent_provider_for_prompt(shell_command)
    if bracketed_paste_used and provider in BRACKETED_PASTE_ENTER_SUBMIT_PROVIDERS:
        return b"\n"
    if provider in COMPOSER_SUBMIT_PROVIDERS:
        return AGENT_COMPOSER_SUBMIT_INPUT
    return b"\n"


def agent_prompt_followup_submit_bytes(shell_command: str | None) -> bytes | None:
    if agent_provider_for_prompt(shell_command) in FOLLOWUP_COMPOSER_SUBMIT_PROVIDERS:
        return AGENT_COMPOSER_SUBMIT_INPUT
    return None


def agent_provider_for_prompt(shell_command: str | None) -> str | None:
    provider = agent_provider_from_command(shell_command)
    if provider is not None:
        return provider
    if shell_command and "codex" in shell_command.lower():
        return "codex"
    return None


def looks_like_agent_command(shell_command: str) -> bool:
    if agent_provider_from_command(shell_command) is not None:
        return True
    lowered = shell_command.lower()
    return any(token in lowered for token in ("codex", "claude", "agent", "cursor", "agy"))


def normalize_terminal_text(output: str) -> str:
    return _ANSI_ESCAPE.sub("", output).replace("\r", "\n")


def terminal_has_prompt_marker(text: str, markers: tuple[str, ...]) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if any(line_has_prompt_marker(stripped, marker) for marker in markers):
            return True
    return False


def line_has_prompt_marker(line: str, marker: str) -> bool:
    if line == marker:
        return True
    if not line.startswith(marker):
        return False
    remainder = line[len(marker):]
    return bool(remainder) and remainder[0].isspace()
