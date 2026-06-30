from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contexts.activity.api.schemas import AgentTokenUsageCountsOut, AgentTokenUsageOut
from app.models import Event
from app.platform.plugins.agent_tools import agent_activity_source_types


@dataclass(frozen=True)
class TokenUsageCounts:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    reasoning_output_tokens: int = 0

    def has_any(self) -> bool:
        return any(
            value > 0
            for value in (
                self.input_tokens,
                self.output_tokens,
                self.total_tokens,
                self.cached_input_tokens,
                self.cache_creation_input_tokens,
                self.reasoning_output_tokens,
            )
        )

    def plus(self, other: TokenUsageCounts) -> TokenUsageCounts:
        return TokenUsageCounts(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            reasoning_output_tokens=self.reasoning_output_tokens + other.reasoning_output_tokens,
        )


@dataclass(frozen=True)
class TokenUsageSnapshot:
    context: TokenUsageCounts | None
    total: TokenUsageCounts
    context_window: int | None = None
    auto_compact_token_limit: int | None = None


def token_usage_from_payload(payload: dict[str, Any]) -> TokenUsageSnapshot | None:
    statusline_snapshot = _snapshot_from_cursor_statusline(payload)
    if statusline_snapshot is not None:
        return statusline_snapshot

    otel_counts = _counts_from_claude_code_otel_metric(payload)
    if otel_counts is not None:
        return TokenUsageSnapshot(
            context=otel_counts,
            total=otel_counts,
            context_window=_positive_int(payload.get("model_context_window")),
            auto_compact_token_limit=_auto_compact_token_limit(payload),
        )

    candidates = _usage_candidates(payload)
    latest_context: TokenUsageCounts | None = None
    latest_total: TokenUsageCounts | None = None
    incremental_total = TokenUsageCounts()
    context_window = _positive_int(payload.get("model_context_window"))
    auto_compact_token_limit = _auto_compact_token_limit(payload)

    for candidate in candidates:
        context_window = context_window or _positive_int(candidate.get("model_context_window"))
        auto_compact_token_limit = auto_compact_token_limit or _auto_compact_token_limit(candidate)
        context_counts = _counts_from_usage(candidate, "last")
        total_counts = _counts_from_usage(candidate, "total")
        direct_counts = _counts_from_usage(candidate, "direct")

        if context_counts is not None:
            latest_context = context_counts
        if total_counts is not None:
            latest_total = total_counts
        elif direct_counts is not None:
            incremental_total = incremental_total.plus(direct_counts)
            latest_context = direct_counts

    if latest_total is None:
        latest_total = incremental_total if incremental_total.has_any() else latest_context
    if latest_total is None or not latest_total.has_any():
        return None

    return TokenUsageSnapshot(
        context=latest_context,
        total=latest_total,
        context_window=context_window,
        auto_compact_token_limit=auto_compact_token_limit,
    )


async def load_agent_token_usage_for_window(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
) -> AgentTokenUsageOut | None:
    events = list(
        await session.scalars(
            agent_token_usage_events_statement(client_id=client_id, window_id=window_id)
        )
    )
    return agent_token_usage_from_events(events)


def agent_token_usage_events_statement(*, client_id: UUID, window_id: UUID):
    return (
        select(Event)
        .options(selectinload(Event.ai_session))
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id == window_id,
            Event.source_type.in_(agent_activity_source_types()),
            Event.kind != "terminal_output",
        )
        .order_by(Event.created_at, Event.id)
    )


def agent_token_usage_from_events(events: list[Event]) -> AgentTokenUsageOut | None:
    context: TokenUsageCounts | None = None
    total = TokenUsageCounts()
    snapshot_totals: dict[str, TokenUsageCounts] = {}
    context_window: int | None = None
    auto_compact_token_limit: int | None = None
    latest_event_at: datetime | None = None
    providers: set[str] = set()
    event_count = 0

    for event in events:
        snapshot = token_usage_from_payload(event.payload_json)
        if snapshot is None:
            continue
        event_count += 1
        provider = _provider_for_event(event)
        if provider is not None:
            providers.add(provider)
        if snapshot.context is not None:
            context = snapshot.context
        if snapshot.context_window is not None:
            context_window = snapshot.context_window
        if snapshot.auto_compact_token_limit is not None:
            auto_compact_token_limit = snapshot.auto_compact_token_limit
        if _is_cumulative_usage_event(event.payload_json):
            snapshot_totals[_snapshot_key(event, provider)] = snapshot.total
        else:
            total = total.plus(snapshot.total)
        latest_event_at = event.created_at

    for snapshot_total in snapshot_totals.values():
        total = total.plus(snapshot_total)
    if not total.has_any() and context is None:
        return None

    return AgentTokenUsageOut(
        context=_counts_out(context) if context is not None else None,
        total=_counts_out(total),
        context_window=context_window,
        auto_compact_token_limit=auto_compact_token_limit,
        latest_event_at=latest_event_at,
        providers=sorted(providers),
        event_count=event_count,
    )


def payload_is_token_usage_only(payload: dict[str, Any]) -> bool:
    if payload.get("provider") == "cursor_cli" and payload.get("type") == "statusline_token_usage":
        return True
    raw_type = _text(payload.get("raw_type")) or _text(payload.get("name")) or _text(payload.get("type"))
    item = _item(payload)
    return raw_type == "event_msg" and _text(item.get("type")) == "token_count"


def _snapshot_from_cursor_statusline(payload: dict[str, Any]) -> TokenUsageSnapshot | None:
    if payload.get("provider") != "cursor_cli" or payload.get("type") != "statusline_token_usage":
        return None
    context_window = payload.get("context_window")
    if not isinstance(context_window, dict):
        return None

    current_usage = payload.get("current_usage")
    if not isinstance(current_usage, dict):
        current_usage = context_window.get("current_usage")
    current_usage = current_usage if isinstance(current_usage, dict) else {}

    context_input = _positive_int(context_window.get("total_input_tokens"))
    context_output = _positive_int(context_window.get("total_output_tokens"))
    current_counts = _counts_from_usage(current_usage, "direct")
    context_counts = TokenUsageCounts(
        input_tokens=context_input or (current_counts.input_tokens if current_counts else 0),
        output_tokens=current_counts.output_tokens if current_counts else 0,
        total_tokens=context_input or (current_counts.total_tokens if current_counts else 0),
        cached_input_tokens=0,
        cache_creation_input_tokens=0,
        reasoning_output_tokens=current_counts.reasoning_output_tokens if current_counts else 0,
    )
    if not context_counts.has_any():
        return None

    total_counts = TokenUsageCounts(
        input_tokens=context_input or context_counts.input_tokens,
        output_tokens=context_output or context_counts.output_tokens,
        total_tokens=(context_input or 0) + (context_output or 0) or context_counts.total_tokens,
        cached_input_tokens=current_counts.cached_input_tokens if current_counts else 0,
        cache_creation_input_tokens=current_counts.cache_creation_input_tokens if current_counts else 0,
        reasoning_output_tokens=current_counts.reasoning_output_tokens if current_counts else 0,
    )
    return TokenUsageSnapshot(
        context=context_counts,
        total=total_counts,
        context_window=_positive_int(context_window.get("context_window_size")),
        auto_compact_token_limit=None,
    )


def _usage_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    _append_dict(candidates, payload)
    item = _item(payload)
    if item is not payload:
        _append_dict(candidates, item)
    for key in ("message", "raw_message", "response", "result"):
        nested = item.get(key)
        if isinstance(nested, dict):
            _append_dict(candidates, nested)
            usage = nested.get("usage")
            if isinstance(usage, dict):
                _append_dict(candidates, usage)
    info = item.get("info")
    if isinstance(info, dict):
        _append_dict(candidates, info)
    usage = item.get("usage")
    if isinstance(usage, dict):
        _append_dict(candidates, usage)
    if isinstance(info, dict):
        usage = info.get("usage")
        if isinstance(usage, dict):
            _append_dict(candidates, usage)
    return candidates


def _append_dict(candidates: list[dict[str, Any]], value: dict[str, Any]) -> None:
    if value not in candidates:
        candidates.append(value)


def _counts_from_usage(value: dict[str, Any], mode: str) -> TokenUsageCounts | None:
    if mode == "last":
        nested = _first_dict(value, "last_token_usage", "lastTokenUsage", "context_usage", "contextUsage")
        return _counts_from_usage(nested, "direct") if nested is not None else None
    if mode == "total":
        nested = _first_dict(value, "total_token_usage", "totalTokenUsage", "total_usage", "totalUsage")
        return _counts_from_usage(nested, "direct") if nested is not None else None

    counts = TokenUsageCounts(
        input_tokens=_usage_int(value, "input_tokens", "inputTokens", "prompt_tokens", "promptTokens"),
        output_tokens=_usage_int(value, "output_tokens", "outputTokens", "completion_tokens", "completionTokens"),
        total_tokens=_usage_int(value, "total_tokens", "totalTokens"),
        cached_input_tokens=_usage_int(
            value,
            "cached_input_tokens",
            "cachedInputTokens",
            "cache_read_input_tokens",
            "cacheReadInputTokens",
            "cacheReadTokens",
            "prompt_cache_hit_tokens",
            "promptCacheHitTokens",
        ),
        cache_creation_input_tokens=_usage_int(
            value,
            "cache_creation_input_tokens",
            "cacheCreationInputTokens",
            "cacheWriteTokens",
            "prompt_cache_miss_tokens",
            "promptCacheMissTokens",
        ),
        reasoning_output_tokens=_usage_int(
            value,
            "reasoning_output_tokens",
            "reasoningOutputTokens",
        ),
    )
    if counts.total_tokens == 0 and (counts.input_tokens > 0 or counts.output_tokens > 0):
        extra_cache_tokens = (
            counts.cached_input_tokens + counts.cache_creation_input_tokens
            if _has_separate_cache_token_fields(value)
            else 0
        )
        counts = TokenUsageCounts(
            input_tokens=counts.input_tokens,
            output_tokens=counts.output_tokens,
            total_tokens=counts.input_tokens + counts.output_tokens + extra_cache_tokens,
            cached_input_tokens=counts.cached_input_tokens,
            cache_creation_input_tokens=counts.cache_creation_input_tokens,
            reasoning_output_tokens=counts.reasoning_output_tokens,
        )
    return counts if counts.has_any() else None


def _counts_from_claude_code_otel_metric(payload: dict[str, Any]) -> TokenUsageCounts | None:
    if payload.get("name") != "claude_code.token.usage":
        return None
    attributes = payload.get("attributes")
    if not isinstance(attributes, dict):
        return None
    token_type = attributes.get("type")
    value = _positive_int(payload.get("value"))
    if not isinstance(token_type, str) or value is None or value <= 0:
        return None
    if token_type == "input":
        return TokenUsageCounts(input_tokens=value, total_tokens=value)
    if token_type == "output":
        return TokenUsageCounts(output_tokens=value, total_tokens=value)
    if token_type == "cacheRead":
        return TokenUsageCounts(cached_input_tokens=value, total_tokens=value)
    if token_type == "cacheCreation":
        return TokenUsageCounts(cache_creation_input_tokens=value, total_tokens=value)
    return None


def _first_dict(value: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        nested = value.get(key)
        if isinstance(nested, dict):
            return nested
    return None


def _usage_int(value: dict[str, Any], *keys: str) -> int:
    for key in keys:
        parsed = _positive_int(value.get(key))
        if parsed is not None:
            return parsed
    return 0


def _auto_compact_token_limit(value: dict[str, Any]) -> int | None:
    return (
        _positive_int(value.get("model_auto_compact_token_limit"))
        or _positive_int(value.get("auto_compact_token_limit"))
    )


def _has_separate_cache_token_fields(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "cache_read_input_tokens",
            "cacheReadInputTokens",
            "cacheReadTokens",
            "cache_creation_input_tokens",
            "cacheCreationInputTokens",
            "cacheWriteTokens",
        )
    )


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _is_cumulative_usage_event(payload: dict[str, Any]) -> bool:
    if not payload_is_token_usage_only(payload):
        return False
    item = _item(payload)
    info = item.get("info")
    return isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict)


def _item(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else payload


def _provider_for_event(event: Event) -> str | None:
    if event.ai_session is not None and event.ai_session.provider:
        return event.ai_session.provider
    provider = event.payload_json.get("provider")
    return provider.strip() if isinstance(provider, str) and provider.strip() else None


def _snapshot_key(event: Event, provider: str | None) -> str:
    if event.ai_session_id is not None:
        return f"ai_session:{event.ai_session_id}"
    return f"{provider or event.source_type.value}:{event.source_id}"


def _counts_out(counts: TokenUsageCounts) -> AgentTokenUsageCountsOut:
    return AgentTokenUsageCountsOut(
        input_tokens=counts.input_tokens,
        output_tokens=counts.output_tokens,
        total_tokens=counts.total_tokens,
        cached_input_tokens=counts.cached_input_tokens,
        cache_creation_input_tokens=counts.cache_creation_input_tokens,
        reasoning_output_tokens=counts.reasoning_output_tokens,
    )


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
