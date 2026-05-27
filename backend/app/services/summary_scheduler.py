from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools import agent_activity_source_types, get_agent_tool_registry
from app.config import get_settings
from app.models import Event, SummaryJob, SummaryJobStatus, VirtualWindow
from app.services.terminal_work_status import RECENT_ACTIVE_WINDOW_SECONDS
from app.services.window_runtime_tags import agent_from_command

INPUT_IDLE_REASON = "input_idle"
INPUT_INITIAL_MAX_WAIT_REASON = "input_initial_max_wait"
INPUT_REPEAT_REASON = "input_repeat"
AGENT_IDLE_REASON = "agent_idle"
TERMINAL_INPUT_COMMAND_KIND = "terminal_input_command"
TERMINAL_OUTPUT_KIND = "terminal_output"
TERMINAL_COMMAND_FINISHED_KIND = "terminal_command_finished"
AGENT_WORK_PRESENCE_KIND = "agent_work_presence"


async def schedule_summary_after_terminal_input(
    session: AsyncSession,
    window: VirtualWindow,
    *,
    now: datetime | None = None,
) -> SummaryJob | None:
    """Schedule a summary after shell user input goes idle."""
    del now

    input_events = await _terminal_input_events(session, window.id)
    input_times = [_event_input_time(event) for event in input_events]
    if not input_times:
        return None
    if _latest_command_agent(input_events) is not None:
        return None

    settings = get_settings()
    first_input_at = input_times[0]
    last_input_at = input_times[-1]
    last_summary_at = await _last_summary_at(session, window.id)

    if last_summary_at is None:
        idle_run_after = last_input_at + timedelta(seconds=settings.terminal_summary_idle_seconds)
        max_wait_run_after = first_input_at + timedelta(
            seconds=settings.terminal_summary_initial_max_wait_seconds
        )
        run_after = min(max_wait_run_after, idle_run_after)
        trigger_reason = (
            INPUT_INITIAL_MAX_WAIT_REASON if max_wait_run_after < idle_run_after else INPUT_IDLE_REASON
        )
    else:
        idle_run_after = last_input_at + timedelta(seconds=settings.terminal_summary_idle_seconds)
        repeat_run_after = last_summary_at + timedelta(seconds=settings.terminal_summary_repeat_seconds)
        run_after = min(repeat_run_after, idle_run_after)
        trigger_reason = INPUT_REPEAT_REASON if repeat_run_after <= idle_run_after else INPUT_IDLE_REASON

    input_generation = len(input_times)
    pending_job = await _pending_summary_job(session, window.id)
    if pending_job is None:
        pending_job = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.pending,
        )
        session.add(pending_job)

    pending_job.run_after = run_after
    pending_job.trigger_reason = trigger_reason
    pending_job.input_generation = input_generation
    await session.flush()
    return pending_job


async def schedule_summary_after_agent_activity(
    session: AsyncSession,
    window: VirtualWindow,
    *,
    now: datetime | None = None,
) -> SummaryJob | None:
    """Schedule a summary after user agent chat or long-idle assistant activity."""
    del now

    user_message_job = await _schedule_after_latest_agent_user_message(session, window)
    if user_message_job is not None:
        return user_message_job

    burst_start = await _current_agent_burst_start(session, window.id)
    if burst_start is None:
        return None
    if not await _was_idle_before(session, window.id, burst_start):
        return None

    last_summary_at = await _last_summary_at(session, window.id)
    if last_summary_at is not None and last_summary_at >= burst_start:
        return None

    last_activity_at = await _last_agent_activity_at(session, window.id)
    if last_activity_at is None:
        return None

    settings = get_settings()
    run_after = last_activity_at + timedelta(seconds=settings.terminal_summary_idle_seconds)

    pending_job = await _pending_summary_job(session, window.id)
    if pending_job is None:
        pending_job = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.pending,
        )
        session.add(pending_job)

    pending_job.run_after = run_after
    pending_job.trigger_reason = AGENT_IDLE_REASON
    pending_job.input_generation = await _agent_activity_generation(session, window.id)
    await session.flush()
    return pending_job


async def _schedule_after_latest_agent_user_message(
    session: AsyncSession,
    window: VirtualWindow,
) -> SummaryJob | None:
    user_message_events = await _agent_user_message_events(session, window.id)
    if not user_message_events:
        return None

    latest_user_message_at = _ensure_aware(user_message_events[-1].created_at)
    last_summary_at = await _last_summary_at(session, window.id)
    if last_summary_at is not None and last_summary_at >= latest_user_message_at:
        return None

    settings = get_settings()
    run_after = latest_user_message_at + timedelta(seconds=settings.terminal_summary_idle_seconds)

    pending_job = await _pending_summary_job(session, window.id)
    if pending_job is None:
        pending_job = SummaryJob(
            virtual_window_id=window.id,
            status=SummaryJobStatus.pending,
        )
        session.add(pending_job)

    pending_job.run_after = run_after
    pending_job.trigger_reason = AGENT_IDLE_REASON
    pending_job.input_generation = await _agent_activity_generation(session, window.id)
    await session.flush()
    return pending_job


async def _terminal_input_events(session: AsyncSession, window_id: UUID) -> list[Event]:
    return list(
        await session.scalars(
            select(Event)
            .where(
                Event.virtual_window_id == window_id,
                Event.kind == TERMINAL_INPUT_COMMAND_KIND,
            )
            .order_by(Event.created_at, Event.id)
        )
    )


async def _agent_user_message_events(session: AsyncSession, window_id: UUID) -> list[Event]:
    events = list(
        await session.scalars(
            select(Event)
            .where(
                Event.virtual_window_id == window_id,
                Event.source_type.in_(agent_activity_source_types()),
            )
            .order_by(Event.created_at, Event.id)
        )
    )
    return [event for event in events if _is_agent_user_message(event)]


def _is_agent_user_message(event: Event) -> bool:
    provider = event.payload_json.get("provider")
    provider_name = provider.strip() if isinstance(provider, str) else None
    try:
        adapter = get_agent_tool_registry().by_source_type(event.source_type, provider_name)
    except (KeyError, ValueError):
        return event.kind in {"user", "user_message"} or _payload_role(event.payload_json) == "user"

    chat = adapter.project_chat(event)
    return chat is not None and chat.role == "user"


def _payload_role(payload: dict) -> str | None:
    role = payload.get("role")
    if isinstance(role, str):
        return role
    message = payload.get("message")
    if isinstance(message, dict):
        message_role = message.get("role")
        if isinstance(message_role, str):
            return message_role
    return None


def _latest_command_agent(input_events: list[Event]) -> str | None:
    if not input_events:
        return None
    command = input_events[-1].payload_json.get("command")
    return agent_from_command(command if isinstance(command, str) else None)


def _event_input_time(event: Event) -> datetime:
    captured_at = event.payload_json.get("captured_at")
    if isinstance(captured_at, str):
        try:
            return _ensure_aware(datetime.fromisoformat(captured_at))
        except ValueError:
            pass
    return _ensure_aware(event.created_at)


async def _current_agent_burst_start(session: AsyncSession, window_id: UUID) -> datetime | None:
    activity_times = await _agent_activity_times(session, window_id)
    if not activity_times:
        return None

    gap = timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS)
    burst_start = activity_times[-1]
    for index in range(len(activity_times) - 1, 0, -1):
        current = activity_times[index]
        previous = activity_times[index - 1]
        if current - previous > gap:
            burst_start = current
            break
    else:
        burst_start = activity_times[0]
    return burst_start


async def _was_idle_before(session: AsyncSession, window_id: UUID, moment: datetime) -> bool:
    moment_aware = _ensure_aware(moment)
    rows = await session.scalars(
        select(Event.created_at).where(
            Event.virtual_window_id == window_id,
            or_(
                Event.kind.in_(
                    [
                        TERMINAL_INPUT_COMMAND_KIND,
                        TERMINAL_OUTPUT_KIND,
                        TERMINAL_COMMAND_FINISHED_KIND,
                        AGENT_WORK_PRESENCE_KIND,
                    ]
                ),
                Event.source_type.in_(agent_activity_source_types()),
            ),
        )
    )
    prior_times = [
        _ensure_aware(created_at)
        for created_at in rows
        if created_at is not None and _ensure_aware(created_at) < moment_aware
    ]
    if not prior_times:
        return True
    latest_prior = max(prior_times)
    return moment_aware - latest_prior > timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS)


async def _agent_activity_times(session: AsyncSession, window_id: UUID) -> list[datetime]:
    rows = await session.execute(
        select(Event.created_at)
        .where(
            Event.virtual_window_id == window_id,
            or_(
                Event.kind == AGENT_WORK_PRESENCE_KIND,
                Event.source_type.in_(agent_activity_source_types()),
            ),
        )
        .order_by(Event.created_at, Event.id)
    )
    times: list[datetime] = []
    for (created_at,) in rows:
        if created_at is None:
            continue
        aware = _ensure_aware(created_at)
        if not times or aware != times[-1]:
            times.append(aware)

    command_events = list(
        await session.scalars(
            select(Event)
            .where(
                Event.virtual_window_id == window_id,
                Event.kind == TERMINAL_INPUT_COMMAND_KIND,
            )
            .order_by(Event.created_at, Event.id)
        )
    )
    for event in command_events:
        command = event.payload_json.get("command")
        if agent_from_command(command if isinstance(command, str) else None) is None:
            continue
        aware = _ensure_aware(event.created_at)
        if not times or aware != times[-1]:
            times.append(aware)

    times.sort()
    return times


async def _last_agent_activity_at(session: AsyncSession, window_id: UUID) -> datetime | None:
    times = await _agent_activity_times(session, window_id)
    if not times:
        return None
    return times[-1]


async def _agent_activity_generation(session: AsyncSession, window_id: UUID) -> int:
    return len(await _agent_activity_times(session, window_id))


async def _last_summary_at(session: AsyncSession, window_id: UUID) -> datetime | None:
    job = await session.scalar(
        select(SummaryJob)
        .where(
            SummaryJob.virtual_window_id == window_id,
            SummaryJob.status == SummaryJobStatus.succeeded,
        )
        .order_by(desc(SummaryJob.updated_at), desc(SummaryJob.created_at), desc(SummaryJob.id))
        .limit(1)
    )
    if job is None:
        return None
    return _ensure_aware(job.updated_at or job.created_at)


async def _pending_summary_job(session: AsyncSession, window_id: UUID) -> SummaryJob | None:
    return await session.scalar(
        select(SummaryJob)
        .where(
            SummaryJob.virtual_window_id == window_id,
            SummaryJob.status == SummaryJobStatus.pending,
        )
        .order_by(SummaryJob.created_at, SummaryJob.id)
        .limit(1)
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
