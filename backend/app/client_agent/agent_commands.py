from __future__ import annotations

import posixpath
import re
import shlex

from app.agent_plugins import get_agent_plugin_registry

_ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_COMMAND_WRAPPERS = {"command", "env", "sudo"}
_PROXYCHAINS_WRAPPERS = {"proxychains", "proxychains4"}
_PROXYCHAINS_OPTIONS_WITH_VALUE = {"-f"}


def agent_permission_flag(command_name: str | None) -> str | None:
    if not command_name:
        return None
    provider = get_agent_plugin_registry().provider_for_command_name(command_name)
    if provider is None:
        return None
    return get_agent_plugin_registry().by_provider(provider).command.permission_flag


def is_known_agent_command(command_name: str | None) -> bool:
    if not command_name:
        return False
    return get_agent_plugin_registry().provider_for_command_name(command_name) is not None


def agent_provider_from_command(command: str | None) -> str | None:
    command_name = agent_command_name_from_command(command)
    if command_name is None:
        return None
    return get_agent_plugin_registry().provider_for_command_name(command_name)


def agent_command_name_from_command(command: str | None) -> str | None:
    if not command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    command_index = _agent_command_index(tokens)
    if command_index is None:
        return None
    return tokens[command_index]


def format_agent_command(command_name: str, *args: str) -> str:
    tokens = _tokens_with_agent_permission_flag([command_name, *args])
    return " ".join(shlex.quote(token) for token in tokens)


def agent_command_with_permission_flag(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None

    updated = _tokens_with_agent_permission_flag(tokens)
    if updated == tokens and _agent_command_index(tokens) is None:
        return None
    if updated == tokens and " " not in command.strip():
        return None
    return " ".join(shlex.quote(token) for token in updated)


def agent_command_for_interactive_shell(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or _agent_command_index(tokens) is None:
        return None
    return " ".join(shlex.quote(token) for token in _tokens_with_agent_permission_flag(tokens))


def agent_command_with_official_model_flag(command: str, model: str | None) -> str:
    clean_model = (model or "").strip()
    if not clean_model:
        return command
    try:
        tokens = shlex.split(command)
    except ValueError:
        return command
    if not tokens:
        return command
    cleaned = _remove_model_flag_tokens(tokens)
    command_index = _agent_command_index(cleaned)
    if command_index is None:
        return command
    insert_at = command_index + 1
    updated = [*cleaned[:insert_at], "--model", clean_model, *cleaned[insert_at:]]
    return " ".join(shlex.quote(token) for token in updated)


def _remove_model_flag_tokens(tokens: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == "--model":
            skip_next = True
            continue
        if token.startswith("--model="):
            continue
        cleaned.append(token)
    return cleaned


def _tokens_with_agent_permission_flag(tokens: list[str]) -> list[str]:
    command_index = _agent_command_index(tokens)
    if command_index is None:
        return tokens

    flag = agent_permission_flag(tokens[command_index])
    if flag is None or flag in tokens[command_index + 1 :]:
        return tokens

    return [*tokens[: command_index + 1], flag, *tokens[command_index + 1 :]]


def _agent_command_index(tokens: list[str]) -> int | None:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _ENV_ASSIGNMENT_PATTERN.match(token):
            index += 1
            continue
        if token in _COMMAND_WRAPPERS:
            index += 1
            continue
        if posixpath.basename(token) in _PROXYCHAINS_WRAPPERS:
            index = _skip_proxychains_args(tokens, index + 1)
            continue
        if is_known_agent_command(token):
            return index
        return None
    return None


def _skip_proxychains_args(tokens: list[str], index: int) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index + 1
        if not token.startswith("-") or token == "-":
            return index
        if token in _PROXYCHAINS_OPTIONS_WITH_VALUE:
            index += 2
            continue
        index += 1
    return index
