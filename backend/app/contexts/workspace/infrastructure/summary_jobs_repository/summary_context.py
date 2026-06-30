from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings as _default_get_settings
from app.models import Event, EventSourceType, VirtualWindow
from app.platform.plugins.agent_tools import get_agent_tool_registry
from app.platform.plugins.agent_tools.types import AgentChatProjection

MAX_SUMMARY_CONTEXT_PAYLOAD_BYTES = 8192
_PROVIDER_ALIASES = {"claude": "claude_code"}


def _settings():
    from app.contexts.workspace.infrastructure import summary_jobs_repository

    return getattr(summary_jobs_repository, "get_settings", _default_get_settings)()


def _canonical_provider(provider: str) -> str:
    return _PROVIDER_ALIASES.get(provider, provider)


def _legacy_provider_for_source_type(source_type: EventSourceType) -> str | None:
    for adapter in get_agent_tool_registry().all():
        if source_type in adapter.legacy_source_types:
            return adapter.provider_id
    return None


def _ai_event_chat(event: Event) -> AgentChatProjection | None:
    try:
        adapter = get_agent_tool_registry().by_source_type(
            event.source_type,
            provider=_adapter_provider_for_event(event),
        )
        return adapter.project_chat(event)
    except Exception:
        return None


def _bounded_text(text: str) -> str:
    if len(text.encode("utf-8")) <= MAX_SUMMARY_CONTEXT_PAYLOAD_BYTES:
        return text
    encoded = text.encode("utf-8")[:MAX_SUMMARY_CONTEXT_PAYLOAD_BYTES]
    return encoded.decode("utf-8", errors="ignore") + "\n[TRUNCATED]"


def _adapter_provider_for_event(event: Event) -> str | None:
    if event.source_type is not EventSourceType.agent_tool_record:
        return None
    provider = _ai_event_provider(event)
    try:
        get_agent_tool_registry().by_provider(provider)
    except ValueError:
        return None
    return provider


def _ai_event_provider(event: Event) -> str:
    if event.ai_session is not None:
        return event.ai_session.provider

    legacy_provider = _legacy_provider_for_source_type(event.source_type)
    if legacy_provider is not None:
        return legacy_provider

    payload_provider = event.payload_json.get("provider")
    if isinstance(payload_provider, str) and payload_provider.strip():
        return _canonical_provider(payload_provider.strip())

    return event.source_type.value


def _build_terminal_input_context(
    window: VirtualWindow,
    topic_tree: list[dict[str, object]],
    commands: list[dict[str, Any]],
    session_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    budget_bytes = _settings().terminal_summary_input_context_max_bytes
    topic_tree_text = _render_topic_tree_context(topic_tree)
    included_commands = list(commands)
    included_session_messages = list(session_messages)
    total_commands = len(commands)
    total_session_messages = len(session_messages)
    commands_truncated = False
    session_messages_truncated = False

    while True:
        item = _terminal_input_context_item(
            window,
            topic_tree_text,
            included_commands,
            included_session_messages,
            total_commands=total_commands,
            total_session_messages=total_session_messages,
            commands_truncated=commands_truncated,
            session_messages_truncated=session_messages_truncated,
            budget_bytes=budget_bytes,
        )
        if _serialized_size(item) <= budget_bytes:
            return item
        pruned_topic_tree_item = _terminal_input_context_item_with_pruned_topic_tree(
            window,
            topic_tree,
            included_commands,
            included_session_messages,
            total_commands=total_commands,
            total_session_messages=total_session_messages,
            commands_truncated=commands_truncated,
            session_messages_truncated=session_messages_truncated,
            budget_bytes=budget_bytes,
        )
        if _serialized_size(pruned_topic_tree_item) <= budget_bytes:
            return pruned_topic_tree_item
        trimmed_session_messages = _without_oldest_non_user_session_message(included_session_messages)
        if len(trimmed_session_messages) < len(included_session_messages):
            included_session_messages = trimmed_session_messages
            session_messages_truncated = True
            continue
        if included_commands:
            included_commands = included_commands[1:]
            commands_truncated = True
            continue
        if included_session_messages:
            included_session_messages = included_session_messages[1:]
            session_messages_truncated = True
            continue
        return pruned_topic_tree_item


def _terminal_input_context_item_with_pruned_topic_tree(
    window: VirtualWindow,
    topic_tree: list[dict[str, object]],
    commands: list[dict[str, Any]],
    session_messages: list[dict[str, Any]],
    *,
    total_commands: int,
    total_session_messages: int,
    commands_truncated: bool,
    session_messages_truncated: bool,
    budget_bytes: int,
) -> dict[str, Any]:
    pruned_topic_tree_lines = ["/"]

    def build_item() -> dict[str, Any]:
        return _terminal_input_context_item(
            window,
            "\n".join(pruned_topic_tree_lines),
            commands,
            session_messages,
            total_commands=total_commands,
            total_session_messages=total_session_messages,
            commands_truncated=commands_truncated,
            session_messages_truncated=session_messages_truncated,
            budget_bytes=budget_bytes,
            topic_tree_truncated=True,
        )

    def fits_budget() -> bool:
        return _serialized_size(build_item()) <= budget_bytes

    for index, root in enumerate(topic_tree):
        included = _include_topic_tree_text_node_until_budget(
            pruned_topic_tree_lines,
            root,
            "",
            index == len(topic_tree) - 1,
            fits_budget,
        )
        if not included:
            break

    return build_item()


def _render_topic_tree_context(topic_tree: list[dict[str, object]]) -> str:
    lines = ["/"]
    for index, root in enumerate(topic_tree):
        _append_topic_tree_text_node(
            lines,
            root,
            "",
            index == len(topic_tree) - 1,
        )
    return "\n".join(lines)


def _include_topic_tree_text_node_until_budget(
    lines: list[str],
    node: dict[str, object],
    prefix: str,
    is_last: bool,
    fits_budget: Callable[[], bool],
) -> bool:
    lines.append(_topic_tree_text_line(node, prefix, is_last))
    if not fits_budget():
        lines.pop()
        return False

    _include_topic_tree_text_children_until_budget(
        lines,
        _topic_tree_node_children(node),
        _child_topic_tree_prefix(prefix, is_last),
        fits_budget,
    )
    return True


def _include_topic_tree_text_children_until_budget(
    lines: list[str],
    children: list[dict[str, object]],
    prefix: str,
    fits_budget: Callable[[], bool],
) -> None:
    for index, child in enumerate(children):
        included = _include_topic_tree_text_node_until_budget(
            lines,
            child,
            prefix,
            index == len(children) - 1,
            fits_budget,
        )
        if not included:
            break


def _append_topic_tree_text_node(
    lines: list[str],
    node: dict[str, object],
    prefix: str,
    is_last: bool,
) -> None:
    lines.append(_topic_tree_text_line(node, prefix, is_last))
    children = _topic_tree_node_children(node)
    for index, child in enumerate(children):
        _append_topic_tree_text_node(
            lines,
            child,
            _child_topic_tree_prefix(prefix, is_last),
            index == len(children) - 1,
        )


def _topic_tree_text_line(node: dict[str, object], prefix: str, is_last: bool) -> str:
    connector = "`- " if is_last else "|- "
    node_type = "leaf" if node.get("is_leaf") is True else "branch"
    return f"{prefix}{connector}{_topic_tree_node_name(node)} [{node_type} t={node.get('terminal_count', 0)}]"


def _child_topic_tree_prefix(prefix: str, is_last: bool) -> str:
    return prefix + ("   " if is_last else "|  ")


def _topic_tree_node_name(node: dict[str, object]) -> str:
    name = node.get("name")
    if isinstance(name, str) and name:
        return name

    path = node.get("path")
    if isinstance(path, str) and path:
        return path.rstrip("/").rsplit("/", 1)[-1] or path
    return "(unnamed)"


def _topic_tree_node_children(node: dict[str, object]) -> list[dict[str, object]]:
    children = node.get("children")
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, dict)]


def _without_oldest_non_user_session_message(
    session_messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    for index, message in enumerate(session_messages):
        if message.get("role") != "user":
            return session_messages[:index] + session_messages[index + 1 :]
    return session_messages


def _terminal_input_context_item(
    window: VirtualWindow,
    topic_tree: str,
    commands: list[dict[str, Any]],
    session_messages: list[dict[str, Any]],
    *,
    total_commands: int,
    total_session_messages: int,
    commands_truncated: bool,
    session_messages_truncated: bool,
    budget_bytes: int,
    topic_tree_truncated: bool = False,
    today: Any | None = None,
) -> dict[str, Any]:
    current_date = today or datetime.now(timezone.utc).date()
    year_month_day = current_date.strftime("%Y-%m-%d")
    year_month = current_date.strftime("%Y-%m")
    return {
        "source_type": "terminal",
        "kind": "terminal_input_context",
        "payload": {
            "window": {
                "id": str(window.id),
                "title": window.title,
                "status": window.status.value,
                "cwd": window.cwd,
                "shell_command": window.shell_command,
                "summary": window.summary,
                "title_tags": window.title_tags,
            },
            "date": {
                "current_date": year_month_day,
                "year_month": year_month,
                "year_month_day": year_month_day,
            },
            "topic_tree": topic_tree,
            "topic_tree_truncation": {
                "truncated": topic_tree_truncated,
                "budget_bytes": budget_bytes,
            },
            "summary_output_language": _settings().summary_output_language,
            "commands": commands,
            "session_messages": session_messages,
            "truncation": {
                "total_commands": total_commands,
                "included_commands": len(commands),
                "truncated": commands_truncated or len(commands) < total_commands,
                "budget_bytes": budget_bytes,
            },
            "session_message_truncation": {
                "total_messages": total_session_messages,
                "included_messages": len(session_messages),
                "truncated": session_messages_truncated
                or len(session_messages) < total_session_messages,
                "budget_bytes": budget_bytes,
            },
        },
    }


def _serialized_size(item: dict[str, Any]) -> int:
    return len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
