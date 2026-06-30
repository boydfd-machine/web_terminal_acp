from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import case

from app.contexts.windows.api.schemas import AgentChatMessageOut
from app.models import Event, EventSourceType
from app.platform.plugins.agent_tools.types import AgentChatProjection

AgentChatOrder = Literal["earliest", "latest"]


@dataclass(frozen=True)
class ChatMessagePage:
    messages: list[AgentChatMessageOut]
    total: int
    total_exact: bool
    has_more: bool


def chat_event_order_by(messages_order: AgentChatOrder) -> tuple[object, ...]:
    tie_breaker = case((Event.source_type == EventSourceType.terminal, 1), else_=0)
    if messages_order == "latest":
        return (Event.created_at.desc(), tie_breaker.desc(), Event.id.desc())
    return (Event.created_at, tie_breaker, Event.id)


def has_unresolved_leading_duplicate(
    items: list[tuple[Event, AgentChatProjection]],
    messages_order: AgentChatOrder,
) -> bool:
    return (
        messages_order == "latest"
        and bool(items)
        and items[0][1].is_duplicate_candidate
        and items[0][1].dedupe_key is not None
    )


def latest_chat_message_page(
    messages: list[AgentChatMessageOut],
    *,
    messages_limit: int,
    messages_offset: int,
    exhausted: bool,
) -> ChatMessagePage:
    start = max(0, len(messages) - (messages_offset + messages_limit))
    paged_messages = messages[start : len(messages) - messages_offset]
    has_more = start > 0 or not exhausted
    total = len(messages) if exhausted else messages_offset + len(paged_messages) + (1 if has_more else 0)
    return ChatMessagePage(
        messages=paged_messages,
        total=total,
        total_exact=exhausted,
        has_more=has_more,
    )
