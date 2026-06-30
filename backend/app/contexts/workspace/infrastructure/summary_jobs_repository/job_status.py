from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import get_settings
from app.models import SummaryJob, SummaryJobStatus

MAX_SUMMARY_JOB_ERROR_LENGTH = 2000
MAX_SUMMARY_JOB_ATTEMPTS = 3
SUMMARY_JOB_RETRY_DELAY_SECONDS = 30


async def get_latest_summary_job(session: AsyncSession, virtual_window_id: UUID) -> SummaryJob | None:
    status_rank = case(
        (SummaryJob.status == SummaryJobStatus.running, 0),
        (SummaryJob.status == SummaryJobStatus.pending, 1),
        else_=2,
    )
    return await session.scalar(
        select(SummaryJob)
        .where(SummaryJob.virtual_window_id == virtual_window_id)
        .order_by(status_rank, desc(SummaryJob.updated_at), desc(SummaryJob.created_at), desc(SummaryJob.id))
        .limit(1)
    )


async def mark_summary_job_succeeded(
    session: AsyncSession,
    job: SummaryJob,
    warning: BaseException | str | None = None,
) -> None:
    job.status = SummaryJobStatus.succeeded
    job.last_error = _bounded_error_message(warning) if warning is not None else None
    job.run_after = None
    await session.flush()


async def mark_summary_job_failed(session: AsyncSession, job: SummaryJob, error: BaseException | str) -> None:
    job.status = SummaryJobStatus.failed
    job.last_error = _bounded_error_message(error)
    job.run_after = datetime.now(timezone.utc)
    await session.flush()


async def mark_summary_job_retryable(session: AsyncSession, job: SummaryJob, error: BaseException | str) -> None:
    if job.attempts >= MAX_SUMMARY_JOB_ATTEMPTS:
        await mark_summary_job_failed(session, job, error)
        return
    if await _pending_followup_summary_job(session, job) is not None:
        await mark_summary_job_failed(session, job, error)
        return

    job.status = SummaryJobStatus.pending
    job.last_error = _bounded_error_message(error)
    job.run_after = datetime.now(timezone.utc) + timedelta(seconds=SUMMARY_JOB_RETRY_DELAY_SECONDS)
    await session.flush()


async def _release_stale_running_jobs_with_due_followups(
    session: AsyncSession,
    now: datetime,
) -> None:
    cutoff = _stale_running_summary_cutoff(now)
    running_job = aliased(SummaryJob)
    pending_followup = (
        select(SummaryJob.id)
        .where(
            SummaryJob.virtual_window_id == running_job.virtual_window_id,
            SummaryJob.status == SummaryJobStatus.pending,
            or_(SummaryJob.run_after.is_(None), SummaryJob.run_after <= now),
        )
        .exists()
    )
    statement = (
        select(running_job)
        .where(
            running_job.status == SummaryJobStatus.running,
            func.coalesce(running_job.updated_at, running_job.created_at) <= cutoff,
            pending_followup,
        )
        .limit(50)
    )
    for job in await session.scalars(statement):
        job.status = SummaryJobStatus.failed
        job.last_error = _bounded_error_message("summary job superseded by pending follow-up")
        job.run_after = now
    await session.flush()


async def _pending_followup_summary_job(session: AsyncSession, job: SummaryJob) -> SummaryJob | None:
    return await session.scalar(
        select(SummaryJob)
        .where(
            SummaryJob.virtual_window_id == job.virtual_window_id,
            SummaryJob.status == SummaryJobStatus.pending,
            SummaryJob.id != job.id,
        )
        .order_by(SummaryJob.created_at, SummaryJob.id)
        .limit(1)
    )


def _stale_running_summary_cutoff(now: datetime) -> datetime:
    settings = get_settings()
    timeout_seconds = max(
        120.0,
        settings.openai_compat_timeout_seconds + SUMMARY_JOB_RETRY_DELAY_SECONDS,
    )
    return now - timedelta(seconds=timeout_seconds)


def _bounded_error_message(error: BaseException | str) -> str:
    message = str(error)
    if len(message) <= MAX_SUMMARY_JOB_ERROR_LENGTH:
        return message
    return message[:MAX_SUMMARY_JOB_ERROR_LENGTH]
