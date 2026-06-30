from __future__ import annotations

import re

_TAG_PATTERNS = (
    re.compile(r"<user_request>\s*(.*?)\s*</user_request>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<objective>\s*(.*?)\s*</objective>", re.DOTALL | re.IGNORECASE),
)

_AGENT_INSTRUCTIONS_SECTION = re.compile(
    r"(^|\n)[ \t]*(?:#\s*)?AGENTS?\.md instructions[^\n]*\n"
    r"(?:[ \t]*\n)*[ \t]*<INSTRUCTIONS>.*?</INSTRUCTIONS>[ \t]*(?=\n|$)",
    re.DOTALL | re.IGNORECASE,
)

_OUTPUT_LANGUAGE_INSTRUCTION_PREFIX = re.compile(
    r"\A\s*System language for agent response:[^\n]*\n"
    r"Write all user-facing responses in this language\.[^\n]*(?:\n{2,}|\Z)",
    re.IGNORECASE,
)

_SYNTHETIC_PREFIXES = (
    "# AGENTS.md instructions for ",
    "# AGENT.md instructions for ",
    "<environment_context>",
    "<goal_context>",
    "<turn_aborted>",
    "<user_info>",
    "<system-reminder>",
    "<system_reminder>",
    "<conversation_summary>",
    "<local-command-caveat>",
    "<bash-input>",
    "<bash-stdout>",
    "<bash-stderr>",
)

_SENSITIVE_PREFIXES = (
    "<encrypted",
    "encrypted:",
    "encrypted ",
    "ciphertext:",
    "-----begin",
)


def extract_real_user_input(text: str | None, *, provider: str | None = None) -> str | None:
    if text is None:
        return None

    stripped = text.strip()
    if not stripped:
        return None

    tagged_parts: list[str] = []
    for pattern in _TAG_PATTERNS:
        tagged_parts.extend(part.strip() for part in pattern.findall(stripped) if part.strip())
    if tagged_parts:
        tagged_input = "\n\n".join(tagged_parts)
        return None if _is_sensitive_message(tagged_input) else tagged_input

    stripped = _strip_synthetic_sections(stripped)
    if not stripped:
        return None

    if _is_synthetic_user_message(stripped, provider=provider):
        return None

    if _is_sensitive_message(stripped):
        return None

    return stripped


def _is_synthetic_user_message(text: str, *, provider: str | None) -> bool:
    lowered = text.lower()
    if any(lowered.startswith(prefix.lower()) for prefix in _SYNTHETIC_PREFIXES):
        return True

    if provider == "cursor_cli" and lowered.startswith("<user_info>"):
        return True

    if re.match(r"# AGENTS?\.md instructions for ", text, re.IGNORECASE) and "<INSTRUCTIONS>" in text:
        return True

    return False


def _strip_synthetic_sections(text: str) -> str:
    stripped = _OUTPUT_LANGUAGE_INSTRUCTION_PREFIX.sub("", text, count=1).strip()
    stripped = _AGENT_INSTRUCTIONS_SECTION.sub("\n", stripped).strip()
    return _squash_excess_blank_lines(stripped)


def _squash_excess_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _is_sensitive_message(text: str) -> bool:
    lowered = text.lower()
    return any(lowered.startswith(prefix) for prefix in _SENSITIVE_PREFIXES)
