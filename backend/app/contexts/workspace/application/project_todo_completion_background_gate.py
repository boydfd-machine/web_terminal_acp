from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.application.project_todo_background_completion import (
    FINAL_COMPLETION_WAITING_PREFIX,
    ensure_aware,
    final_completion_waiting_error,
    todo_waited_for_background_work,
)
from app.contexts.workspace.application.project_todo_completion_prompt import VerificationVerdict
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.models import ProjectTodo


@dataclass(frozen=True)
class BackgroundCompletionReview:
    waited_for_background_work: bool
    completed_at: datetime


async def background_completion_review_time(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    client_id: UUID,
    window_id: UUID,
    completed_at: datetime,
    dispatch_stage: str,
) -> BackgroundCompletionReview | None:
    if not todo_waited_for_background_work(todo.dispatch_error):
        return BackgroundCompletionReview(False, completed_at)
    if final_completion_wait_started_at(todo.dispatch_error) is not None:
        return BackgroundCompletionReview(True, ensure_aware(completed_at))
    later_completed_at = await latest_window_completion_after(
        session,
        client_id=client_id,
        window_id=window_id,
        completed_at=completed_at,
    )
    if later_completed_at is not None:
        return BackgroundCompletionReview(True, later_completed_at)
    todo.dispatch_stage = dispatch_stage
    todo.dispatch_error = final_completion_waiting_error(completed_at)
    return None


async def latest_window_completion_after(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    completed_at: datetime,
) -> datetime | None:
    window = await get_window_for_client(session, client_id, window_id)
    if window is None or window.agent_activity_latest_completed_at is None:
        return None
    latest_completed_at = ensure_aware(window.agent_activity_latest_completed_at)
    if latest_completed_at > ensure_aware(completed_at):
        return latest_completed_at
    return None


def background_verification_incomplete_waiting_error(
    completed_at: datetime,
    *,
    attempt: int,
    verdict: VerificationVerdict,
) -> str:
    detail = f"verification attempt {attempt} {verdict.verdict}: {verdict.evidence}"
    return f"{final_completion_waiting_error(completed_at)}; {detail}"[:4000]


def final_completion_wait_started_at(dispatch_error: str | None) -> datetime | None:
    if not dispatch_error or not dispatch_error.startswith(FINAL_COMPLETION_WAITING_PREFIX):
        return None
    marker = "last agent completion at "
    _prefix, separator, remainder = dispatch_error.partition(marker)
    if separator == "":
        return None
    timestamp = remainder.split(";", 1)[0].strip()
    if not timestamp:
        return None
    try:
        return ensure_aware(datetime.fromisoformat(timestamp))
    except ValueError:
        return None
