import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, asc, desc, or_, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.contexts.workspace.infrastructure.summary_jobs_repository.job_status import (
    _release_stale_running_jobs_with_due_followups,
)
from app.contexts.workspace.infrastructure.summary_jobs_repository.summary_context import (
    _ai_event_chat,
    _bounded_text,
    _build_terminal_input_context,
    _legacy_provider_for_source_type,
)
from app.models import Event, ProjectTodo, SummaryJob, SummaryJobStatus, VirtualWindow
from app.platform.plugins.agent_tools import agent_activity_source_types
from app.contexts.workspace.infrastructure.folders_repository import build_topic_tree_context

_ACTIVE_SUMMARY_JOB_STATUSES = (SummaryJobStatus.pending,)
MAX_SUMMARY_CONTEXT_EVENTS = 50
MAX_SUMMARY_CONTEXT_COMMANDS = 200
MAX_SUMMARY_CONTEXT_PAYLOAD_BYTES = 8192
_PROVIDER_ALIASES = {"claude": "claude_code"}
_ASK_USER_TOOL_NAME_MARKERS = (
    "request_user_input",
    "ask_user",
    "ask_question",
    "user_question",
    "clarifying_question",
)
_ASK_USER_QUESTION_KEYS = ("question", "prompt", "message")


def _canonical_provider(provider: str) -> str:
    return _PROVIDER_ALIASES.get(provider, provider)


def _active_summary_job_query(virtual_window_id: UUID) -> Select[tuple[SummaryJob]]:
    return (
        select(SummaryJob)
        .where(
            SummaryJob.virtual_window_id == virtual_window_id,
            SummaryJob.status.in_(_ACTIVE_SUMMARY_JOB_STATUSES),
        )
        .order_by(SummaryJob.created_at, SummaryJob.id)
    )


async def enqueue_summary_job(
    session: AsyncSession,
    virtual_window_id: UUID,
    *,
    trigger_reason: str | None = None,
    allow_title_folder_override: bool = False,
    input_generation: int = 0,
    run_after: datetime | None = None,
    update_existing: bool = False,
) -> SummaryJob:
    async def update_job(job: SummaryJob) -> None:
        job.status = SummaryJobStatus.pending
        job.trigger_reason = trigger_reason
        job.allow_title_folder_override = allow_title_folder_override
        job.input_generation = input_generation
        job.run_after = run_after
        await session.flush()

    existing_job = await session.scalar(_active_summary_job_query(virtual_window_id))
    if existing_job is not None:
        if update_existing:
            await update_job(existing_job)
        return existing_job

    attempted_native_insert, inserted_job = await _insert_pending_summary_job_on_conflict_do_nothing(
        session,
        virtual_window_id,
        trigger_reason=trigger_reason,
        allow_title_folder_override=allow_title_folder_override,
        input_generation=input_generation,
        run_after=run_after,
    )
    if attempted_native_insert:
        if inserted_job is not None:
            return inserted_job
        existing_job = await session.scalar(_active_summary_job_query(virtual_window_id))
        if existing_job is not None:
            if update_existing:
                await update_job(existing_job)
            return existing_job

    job = SummaryJob(
        virtual_window_id=virtual_window_id,
        status=SummaryJobStatus.pending,
        trigger_reason=trigger_reason,
        allow_title_folder_override=allow_title_folder_override,
        input_generation=input_generation,
        run_after=run_after,
    )
    try:
        async with session.begin_nested():
            session.add(job)
            await session.flush()
    except IntegrityError as exc:
        existing_job = await session.scalar(_active_summary_job_query(virtual_window_id))
        if existing_job is not None:
            if update_existing:
                await update_job(existing_job)
            return existing_job
        await session.rollback()
        raise exc
    return job


async def _insert_pending_summary_job_on_conflict_do_nothing(
    session: AsyncSession,
    virtual_window_id: UUID,
    *,
    trigger_reason: str | None,
    allow_title_folder_override: bool,
    input_generation: int,
    run_after: datetime | None,
) -> tuple[bool, SummaryJob | None]:
    get_bind = getattr(session, "get_bind", None)
    if get_bind is None:
        return False, None
    dialect_name = get_bind().dialect.name
    if dialect_name == "postgresql":
        insert_factory = postgresql_insert
    else:
        return False, None

    job_id = uuid4()
    statement = _pending_summary_job_insert_statement(
        insert_factory,
        job_id,
        virtual_window_id,
        trigger_reason=trigger_reason,
        allow_title_folder_override=allow_title_folder_override,
        input_generation=input_generation,
        run_after=run_after,
    )
    inserted_id = (await session.execute(statement)).scalar_one_or_none()
    if inserted_id is None:
        return True, None
    return True, await session.get(SummaryJob, inserted_id)


def _pending_summary_job_insert_statement(
    insert_factory: Callable,
    job_id: UUID,
    virtual_window_id: UUID,
    *,
    trigger_reason: str | None,
    allow_title_folder_override: bool,
    input_generation: int,
    run_after: datetime | None,
):
    return (
        insert_factory(SummaryJob)
        .values(
            id=job_id,
            virtual_window_id=virtual_window_id,
            status=SummaryJobStatus.pending,
            trigger_reason=trigger_reason,
            allow_title_folder_override=allow_title_folder_override,
            input_generation=input_generation,
            run_after=run_after,
        )
        .on_conflict_do_nothing(
            index_elements=[SummaryJob.virtual_window_id],
            index_where=text("status = 'PENDING'"),
        )
        .returning(SummaryJob.id)
    )


async def enqueue_manual_summary_retry(
    session: AsyncSession,
    virtual_window_id: UUID,
    *,
    allow_title_folder_override: bool = False,
) -> SummaryJob:
    return await enqueue_summary_job(
        session,
        virtual_window_id,
        trigger_reason="manual_retry",
        allow_title_folder_override=allow_title_folder_override,
        run_after=datetime.now(timezone.utc),
        update_existing=True,
    )


async def claim_next_summary_job(session: AsyncSession) -> SummaryJob | None:
    now = datetime.now(timezone.utc)
    await _release_stale_running_jobs_with_due_followups(session, now)
    running_job = aliased(SummaryJob)
    running_same_window = (
        select(running_job.id)
        .where(
            running_job.virtual_window_id == SummaryJob.virtual_window_id,
            running_job.status == SummaryJobStatus.running,
        )
        .exists()
    )
    statement = (
        select(SummaryJob)
        .where(
            SummaryJob.status == SummaryJobStatus.pending,
            or_(SummaryJob.run_after.is_(None), SummaryJob.run_after <= now),
            ~running_same_window,
        )
        .order_by(
            asc(SummaryJob.run_after).nulls_first(),
            SummaryJob.created_at,
            SummaryJob.id,
        )
        .limit(1)
    )

    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    job = await session.scalar(statement)
    if job is None:
        return None

    job.status = SummaryJobStatus.running
    job.attempts += 1
    job.last_error = None
    await session.flush()
    return job


async def collect_summary_context(session: AsyncSession, window: VirtualWindow) -> list[dict[str, Any]]:
    topic_tree = await build_topic_tree_context(session, window.client_id)
    commands, session_messages = await collect_window_activity_context(session, window)

    return [_build_terminal_input_context(window, topic_tree, commands, session_messages)]


async def collect_window_activity_context(
    session: AsyncSession,
    window: VirtualWindow,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    command_events = list(
        await session.scalars(
            select(Event)
            .where(
                Event.client_id == window.client_id,
                Event.virtual_window_id == window.id,
                Event.kind == "terminal_input_command",
            )
            .order_by(desc(Event.created_at), desc(Event.id))
            .limit(MAX_SUMMARY_CONTEXT_COMMANDS)
        )
    )
    commands = [_command_from_event(event, window) for event in reversed(command_events)]
    ai_event_rows = await _recent_ai_events_for_summary(session, window)
    session_messages = [
        session_message
        for event in reversed(ai_event_rows)
        for session_message in _session_messages_from_event(event)
    ]
    todo_messages = await _project_todo_prompt_messages(session, window, session_messages)
    return commands, [*todo_messages, *session_messages]


async def _project_todo_prompt_messages(
    session: AsyncSession,
    window: VirtualWindow,
    session_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if any(message.get("role") == "user" for message in session_messages):
        return []
    todo = await session.scalar(
        select(ProjectTodo)
        .where(
            ProjectTodo.client_id == window.client_id,
            ProjectTodo.assigned_window_id == window.id,
            ProjectTodo.dispatch_prompt.is_not(None),
        )
        .order_by(desc(ProjectTodo.dispatched_at), desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
        .limit(1)
    )
    prompt = todo.dispatch_prompt.strip() if todo is not None and todo.dispatch_prompt else ""
    return [{"role": "user", "content": _bounded_text(prompt)}] if prompt else []


async def _recent_ai_events_for_summary(
    session: AsyncSession,
    window: VirtualWindow,
) -> list[Event]:
    rows: list[Event] = []
    for source_type in agent_activity_source_types():
        rows.extend(
            await session.scalars(
                select(Event)
                .options(selectinload(Event.ai_session))
                .where(
                    Event.client_id == window.client_id,
                    Event.virtual_window_id == window.id,
                    Event.source_type == source_type,
                )
                .order_by(desc(Event.created_at), desc(Event.id))
                .limit(MAX_SUMMARY_CONTEXT_EVENTS)
            )
        )
    return sorted(rows, key=lambda event: (event.created_at, event.id), reverse=True)[
        :MAX_SUMMARY_CONTEXT_EVENTS
    ]


def _command_from_event(event: Event, window: VirtualWindow) -> dict[str, Any]:
    payload = event.payload_json
    captured_at = payload.get("captured_at")
    if captured_at is None and event.created_at is not None:
        captured_at = event.created_at.isoformat()

    return {
        "sequence": payload.get("sequence"),
        "command": payload.get("command", ""),
        "shell": payload.get("shell") or window.shell_command,
        "cwd": payload.get("cwd") or window.cwd,
        "captured_at": captured_at,
    }


def _session_messages_from_event(event: Event) -> list[dict[str, Any]]:
    session_messages: list[dict[str, Any]] = []
    chat = _ai_event_chat(event)
    if chat is not None and chat.agent_message_type != "subagent_call":
        role = "assistant" if chat.role == "agent" else chat.role
        if role in {"user", "assistant"}:
            session_messages.append({"role": role, "content": _bounded_text(chat.body)})

    ask_user_question = _ask_user_question_from_tool_call(event)
    if ask_user_question is not None:
        session_messages.append(ask_user_question)
    return session_messages


def _ask_user_question_from_tool_call(event: Event) -> dict[str, Any] | None:
    tool_name = _tool_call_name(event)
    if tool_name is None or not _is_ask_user_tool_name(tool_name):
        return None

    question_text = _ask_user_question_text(_tool_call_arguments(event))
    if question_text is None:
        return None
    return {
        "role": "tool_call",
        "name": tool_name,
        "content": _bounded_text(question_text),
    }


def _tool_call_name(event: Event) -> str | None:
    payload = event.payload_json
    item = _nested_payload_item(payload)
    content_block = _first_tool_use_content_block(payload)
    candidates = (
        item.get("name"),
        item.get("tool_name"),
        item.get("tool"),
        content_block.get("name") if content_block is not None else None,
        payload.get("name"),
        payload.get("tool_name"),
        payload.get("tool"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    span = payload.get("span")
    if isinstance(span, dict):
        attributes = span.get("attributes")
        if isinstance(attributes, dict):
            for key in ("tool", "tool_name", "name"):
                value = attributes.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _tool_call_arguments(event: Event) -> Any:
    payload = event.payload_json
    item = _nested_payload_item(payload)
    for key in ("arguments", "input", "args", "parameters"):
        if key in item:
            return item[key]
    content_block = _first_tool_use_content_block(payload)
    if content_block is not None:
        for key in ("arguments", "input", "args", "parameters"):
            if key in content_block:
                return content_block[key]
    for key in ("arguments", "input", "args", "parameters"):
        if key in payload:
            return payload[key]

    span = payload.get("span")
    if isinstance(span, dict):
        attributes = span.get("attributes")
        if isinstance(attributes, dict):
            for key in ("arguments", "input", "args", "parameters"):
                if key in attributes:
                    return attributes[key]
    return {}


def _nested_payload_item(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else payload


def _first_tool_use_content_block(payload: dict[str, Any]) -> dict[str, Any] | None:
    message = payload.get("message")
    if isinstance(message, dict) and "content" in message:
        content = message.get("content")
    else:
        content = payload.get("content")

    if isinstance(content, dict):
        block_type = content.get("type")
        return content if block_type == "tool_use" else None
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return block
    return None


def _is_ask_user_tool_name(name: str) -> bool:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in name)
    return any(marker in normalized for marker in _ASK_USER_TOOL_NAME_MARKERS)


def _ask_user_question_text(arguments: Any) -> str | None:
    if isinstance(arguments, str):
        try:
            parsed_arguments = json.loads(arguments)
        except json.JSONDecodeError:
            stripped = arguments.strip()
            return stripped or None
        return _ask_user_question_text(parsed_arguments)

    if isinstance(arguments, dict):
        for key in _ASK_USER_QUESTION_KEYS:
            value = arguments.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        questions = arguments.get("questions")
        if isinstance(questions, list):
            parts = [_ask_user_question_text(question) for question in questions]
            joined = "\n\n".join(part for part in parts if part)
            return joined or None
        return None

    if isinstance(arguments, list):
        parts = [_ask_user_question_text(item) for item in arguments]
        joined = "\n\n".join(part for part in parts if part)
        return joined or None

    return None


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
