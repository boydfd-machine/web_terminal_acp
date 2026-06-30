from __future__ import annotations

import posixpath
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.plugins.agent_tools import agent_activity_source_types
from app.config import get_settings
from app.models import AiSession, Event, SummaryJob, TerminalRecentUsage, VirtualWindow
from app.contexts.activity.api.schemas import (
    AgentSessionOut,
    AgentTokenUsageCountsOut,
    AgentTokenUsageOut,
    GitWorktreeActivityOut,
)
from app.contexts.agent_profiles.application.capabilities import canonical_provider
from app.contexts.windows.api.schemas import SummaryJobOut, WindowOut
from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
    long_idle_work_status,
    to_work_status_out,
)
from app.contexts.activity.application.window_runtime_tags import (
    agent_from_command,
    runtime_tags_for_window,
)


@dataclass(frozen=True)
class WindowOverviewTimestamps:
    last_terminal_command_at: datetime | None = None
    last_agent_event_at: datetime | None = None
    last_recent_usage_at: datetime | None = None
    last_agent_presence_at: datetime | None = None


def command_capture_supported(window: VirtualWindow) -> bool:
    shell = window.shell_command or get_settings().default_shell
    if agent_from_command(shell) is not None:
        shell = get_settings().default_shell
    return posixpath.basename(shell) in {"bash", "zsh"}


def to_summary_job_out(job: SummaryJob | None) -> SummaryJobOut | None:
    if job is None:
        return None
    return SummaryJobOut(
        id=job.id,
        status=job.status.value,
        trigger_reason=job.trigger_reason,
        attempts=job.attempts,
        last_error=job.last_error,
        run_after=job.run_after,
        updated_at=job.updated_at,
        allow_title_folder_override=job.allow_title_folder_override,
    )


def to_window_out(
    window: VirtualWindow,
    summary_job: SummaryJob | None = None,
    runtime_tags: list[str] | None = None,
    work_status: TerminalWorkStatus | None = None,
    overview_timestamps: WindowOverviewTimestamps | None = None,
    git_worktree: GitWorktreeActivityOut | None = None,
    agent_token_usage: AgentTokenUsageOut | None = None,
    agent_model_metadata: dict[str, object] | None = None,
) -> WindowOut:
    timestamps = overview_timestamps or WindowOverviewTimestamps()
    effective_runtime_tags = runtime_tags
    if effective_runtime_tags is None:
        effective_runtime_tags = runtime_tags_for_window(
            window,
            terminal_agent=agent_from_command(window.shell_command),
        )
    effective_work_status = work_status or long_idle_work_status()
    effective_agent_token_usage = token_usage_with_window_model_metadata(
        window,
        agent_token_usage,
        agent_model_metadata=agent_model_metadata or window_agent_config_model_metadata(window),
    )
    return WindowOut(
        id=window.id,
        client_id=window.client_id,
        title=window.title,
        folder_id=window.folder_id,
        parent_window_id=window.parent_window_id,
        root_window_id=window.root_window_id,
        derived_mode=window.derived_mode,
        derived_context=window.derived_context,
        status=window.status.value,
        tmux_session=window.tmux_session,
        tmux_window_id=window.tmux_window_id,
        tmux_window_index=window.tmux_window_index,
        remote_session_id=window.remote_session_id,
        remote_window_id=window.remote_window_id,
        cwd=window.cwd,
        shell_command=window.shell_command,
        title_manually_overridden=window.title_manually_overridden,
        folder_manually_overridden=window.folder_manually_overridden,
        command_capture_supported=command_capture_supported(window),
        summary=window.summary,
        title_tags=window.title_tags,
        runtime_tags=effective_runtime_tags,
        git_worktree=git_worktree,
        agent_token_usage=effective_agent_token_usage,
        work_status=to_work_status_out(effective_work_status),
        summary_job=to_summary_job_out(summary_job),
        created_at=window.created_at,
        last_terminal_command_at=timestamps.last_terminal_command_at,
        last_agent_event_at=timestamps.last_agent_event_at,
        last_active_at=latest_window_active_at(window, effective_work_status, timestamps),
    )


def token_usage_with_window_model_metadata(
    window: VirtualWindow,
    agent_token_usage: AgentTokenUsageOut | None,
    *,
    agent_model_metadata: dict[str, object] | None = None,
) -> AgentTokenUsageOut | None:
    model_metadata = merged_window_agent_model_metadata(window, agent_model_metadata)
    if model_metadata is None:
        return agent_token_usage
    context_window = _positive_int(model_metadata.get("context_window"))
    auto_compact_token_limit = _positive_int(model_metadata.get("auto_compact_token_limit"))
    if context_window is None and auto_compact_token_limit is None:
        return agent_token_usage
    if agent_token_usage is None:
        return AgentTokenUsageOut(
            context=None,
            total=_empty_token_usage_counts(),
            context_window=context_window,
            auto_compact_token_limit=auto_compact_token_limit,
            providers=_merged_providers([], model_metadata),
            event_count=0,
        )
    update = {}
    if agent_token_usage.context_window is None and context_window is not None:
        update["context_window"] = context_window
    if agent_token_usage.auto_compact_token_limit is None and auto_compact_token_limit is not None:
        update["auto_compact_token_limit"] = auto_compact_token_limit
    return agent_token_usage.model_copy(update=update) if update else agent_token_usage


def merged_window_agent_model_metadata(
    window: VirtualWindow,
    agent_model_metadata: dict[str, object] | None = None,
) -> dict[str, object] | None:
    context_metadata = window_agent_model_metadata(window)
    if context_metadata is None:
        return agent_model_metadata
    if agent_model_metadata is None:
        return context_metadata
    merged = dict(agent_model_metadata)
    merged.update(context_metadata)
    return merged


def window_agent_model_metadata(window: VirtualWindow) -> dict[str, object] | None:
    context = window.derived_context if isinstance(window.derived_context, dict) else {}
    agent_model = context.get("agent_model")
    return agent_model if isinstance(agent_model, dict) else None


def window_agent_config_model_metadata(window: VirtualWindow) -> dict[str, object] | None:
    agent = agent_from_command(window.shell_command)
    if agent is None:
        return None
    return agent_config_service.window_agent_model_metadata(agent, window_id=str(window.id))


def _empty_token_usage_counts():
    return AgentTokenUsageCountsOut()


def _metadata_provider(metadata: dict[str, object]) -> str | None:
    provider = metadata.get("provider")
    return provider if isinstance(provider, str) and provider.strip() else None


def _merged_providers(providers: list[str], metadata: dict[str, object]) -> list[str]:
    provider = _metadata_provider(metadata)
    if provider is None or provider in providers:
        return providers
    return sorted([*providers, provider])


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def max_datetime(*values: datetime | None) -> datetime | None:
    candidates = [aware_utc(value) for value in values if value is not None]
    if not candidates:
        return None
    return max(candidates)


def latest_window_active_at(
    window: VirtualWindow,
    work_status: TerminalWorkStatus,
    timestamps: WindowOverviewTimestamps,
) -> datetime:
    return max_datetime(
        window.created_at,
        timestamps.last_recent_usage_at,
        timestamps.last_terminal_command_at,
        timestamps.last_agent_event_at,
        window.terminal_last_output_at,
        timestamps.last_agent_presence_at,
        work_status.last_activity_at,
        work_status.last_working_activity_at,
    ) or aware_utc(window.created_at)


async def load_window_overview_timestamps(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
) -> WindowOverviewTimestamps:
    latest_command_at = await session.scalar(
        select(Event.created_at)
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id == window_id,
            Event.kind == "terminal_input_command",
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
    )
    latest_agent_event_at = await session.scalar(
        select(Event.created_at)
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id == window_id,
            Event.source_type.in_(agent_activity_source_types()),
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
    )
    latest_recent_usage_at = await session.scalar(
        select(TerminalRecentUsage.last_used_at)
        .where(
            TerminalRecentUsage.client_id == client_id,
            TerminalRecentUsage.window_id == window_id,
        )
        .order_by(desc(TerminalRecentUsage.last_used_at), desc(TerminalRecentUsage.id))
        .limit(1)
    )
    latest_agent_presence_at = await session.scalar(
        select(VirtualWindow.agent_presence_latest_at).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id == window_id,
        )
    )
    return WindowOverviewTimestamps(
        last_terminal_command_at=latest_command_at,
        last_agent_event_at=latest_agent_event_at,
        last_recent_usage_at=latest_recent_usage_at,
        last_agent_presence_at=latest_agent_presence_at,
    )


def to_agent_session_out(ai_session: AiSession) -> AgentSessionOut:
    return AgentSessionOut(
        id=ai_session.id,
        provider=ai_session.provider,
        source_id=ai_session.source_id,
        source_path=ai_session.source_path,
        project_path=ai_session.project_path,
        virtual_window_id=ai_session.virtual_window_id,
        title=ai_session.title,
        tags=ai_session.tags,
        summary=ai_session.summary,
        created_at=ai_session.created_at,
        updated_at=ai_session.updated_at,
    )


async def runtime_tags_for_window_out(session: AsyncSession, window: VirtualWindow) -> list[str]:
    latest_ai_session = await latest_ai_session_for_window(session, window)
    latest_command = await latest_terminal_command_payload(session, window)
    terminal_agent = agent_from_command(latest_command.get("command") if latest_command else None)
    return runtime_tags_for_window(
        window,
        ai_session=latest_ai_session,
        terminal_agent=terminal_agent,
    )


async def latest_ai_session_for_window(
    session: AsyncSession,
    window: VirtualWindow,
) -> AiSession | None:
    return await session.scalar(
        select(AiSession)
        .where(
            AiSession.client_id == window.client_id,
            AiSession.virtual_window_id == window.id,
        )
        .order_by(desc(AiSession.updated_at), desc(AiSession.created_at), desc(AiSession.id))
        .limit(1)
    )


async def latest_terminal_command_payload(
    session: AsyncSession,
    window: VirtualWindow,
) -> dict | None:
    payload = await session.scalar(
        select(Event.payload_json)
        .where(
            Event.client_id == window.client_id,
            Event.virtual_window_id == window.id,
            Event.kind == "terminal_input_command",
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
    )
    return payload if isinstance(payload, dict) else None


async def agent_provider_for_window(session: AsyncSession, window: VirtualWindow) -> str | None:
    latest_ai_session = await latest_ai_session_for_window(session, window)
    if latest_ai_session is not None and latest_ai_session.provider:
        return canonical_provider(latest_ai_session.provider)

    latest_command = await latest_terminal_command_payload(session, window)
    terminal_agent = agent_from_command(latest_command.get("command") if latest_command else None)
    if terminal_agent is not None:
        return canonical_provider(terminal_agent)
    shell_agent = agent_from_command(window.shell_command)
    return canonical_provider(shell_agent) if shell_agent is not None else None


async def agent_command_for_window(session: AsyncSession, window: VirtualWindow) -> str | None:
    latest_command = await latest_terminal_command_payload(session, window)
    if latest_command is not None:
        command = latest_command.get("command")
        if isinstance(command, str) and command.strip():
            return command
    return window.shell_command
