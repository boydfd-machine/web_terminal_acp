from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ProjectTodo,
    ProjectTodoReviewRun,
    ProjectTodoReviewTarget,
    ProjectTodoWorkSnapshot,
)


async def create_project_todo_work_snapshot(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    role: str,
    window_id: UUID | None,
    worktree_summary: dict[str, Any] | None,
    captured_at: datetime | None = None,
) -> ProjectTodoWorkSnapshot:
    summary = worktree_summary if isinstance(worktree_summary, dict) else {}
    commits = [item for item in summary.get("commits") or [] if isinstance(item, dict)]
    files = [item for item in summary.get("files") or [] if isinstance(item, dict)]
    snapshot = ProjectTodoWorkSnapshot(
        project_todo_id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        window_id=window_id,
        role=role,
        branch_name=_string(summary.get("branch")),
        base_ref=_string(summary.get("base_ref")),
        base_sha=_string(summary.get("start_head")),
        head_sha=_string(summary.get("end_head")),
        commit_shas_json=[sha for sha in (_string(commit.get("sha")) for commit in commits) if sha],
        diff_stat_json=_diff_stat(summary, commits, files),
        changed_files_json=files,
        dirty_state=_dirty_state(summary),
        captured_at=_aware(captured_at or datetime.now(UTC)),
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def create_local_review_target(
    session: AsyncSession,
    todo: ProjectTodo,
    snapshot: ProjectTodoWorkSnapshot,
) -> ProjectTodoReviewTarget:
    existing = await session.scalar(
        select(ProjectTodoReviewTarget).where(
            ProjectTodoReviewTarget.project_todo_id == todo.id,
            ProjectTodoReviewTarget.work_snapshot_id == snapshot.id,
            ProjectTodoReviewTarget.provider == "LOCAL_CARD",
        )
    )
    if existing is not None:
        return existing
    target = ProjectTodoReviewTarget(
        project_todo_id=todo.id,
        work_snapshot_id=snapshot.id,
        provider="LOCAL_CARD",
        status="OPEN",
        base_sha=snapshot.base_sha,
        head_sha=snapshot.head_sha,
    )
    session.add(target)
    await session.flush()
    return target


async def latest_project_todo_work_snapshot(
    session: AsyncSession,
    todo_id: UUID,
) -> ProjectTodoWorkSnapshot | None:
    return await session.scalar(
        select(ProjectTodoWorkSnapshot)
        .where(ProjectTodoWorkSnapshot.project_todo_id == todo_id)
        .order_by(desc(ProjectTodoWorkSnapshot.captured_at), desc(ProjectTodoWorkSnapshot.id))
        .limit(1)
    )


async def latest_project_todo_review_target(
    session: AsyncSession,
    todo_id: UUID,
) -> ProjectTodoReviewTarget | None:
    return await session.scalar(
        select(ProjectTodoReviewTarget)
        .where(ProjectTodoReviewTarget.project_todo_id == todo_id, ProjectTodoReviewTarget.status == "OPEN")
        .order_by(desc(ProjectTodoReviewTarget.updated_at), desc(ProjectTodoReviewTarget.id))
        .limit(1)
    )


async def list_project_todo_work_snapshots(
    session: AsyncSession,
    todo_id: UUID,
) -> list[ProjectTodoWorkSnapshot]:
    return list(
        await session.scalars(
            select(ProjectTodoWorkSnapshot)
            .where(ProjectTodoWorkSnapshot.project_todo_id == todo_id)
            .order_by(desc(ProjectTodoWorkSnapshot.captured_at), desc(ProjectTodoWorkSnapshot.id))
        )
    )


async def list_project_todo_review_targets(
    session: AsyncSession,
    todo_id: UUID,
) -> list[ProjectTodoReviewTarget]:
    return list(
        await session.scalars(
            select(ProjectTodoReviewTarget)
            .where(ProjectTodoReviewTarget.project_todo_id == todo_id)
            .order_by(desc(ProjectTodoReviewTarget.updated_at), desc(ProjectTodoReviewTarget.id))
        )
    )


async def list_project_todo_review_runs(
    session: AsyncSession,
    todo_id: UUID,
) -> list[ProjectTodoReviewRun]:
    return list(
        await session.scalars(
            select(ProjectTodoReviewRun)
            .where(ProjectTodoReviewRun.project_todo_id == todo_id)
            .order_by(desc(ProjectTodoReviewRun.created_at), desc(ProjectTodoReviewRun.id))
        )
    )


async def create_project_todo_review_run(
    session: AsyncSession,
    todo: ProjectTodo,
    target: ProjectTodoReviewTarget,
    *,
    agent_client: str | None,
    agent_profile_id: str | None,
) -> ProjectTodoReviewRun:
    run = ProjectTodoReviewRun(
        project_todo_id=todo.id,
        review_target_id=target.id,
        agent_client=agent_client,
        agent_profile_id=agent_profile_id,
        status="QUEUED",
    )
    session.add(run)
    await session.flush()
    return run


async def latest_running_review_run_for_window(
    session: AsyncSession,
    window_id: UUID,
) -> ProjectTodoReviewRun | None:
    return await session.scalar(
        select(ProjectTodoReviewRun)
        .where(ProjectTodoReviewRun.review_window_id == window_id, ProjectTodoReviewRun.status == "RUNNING")
        .order_by(desc(ProjectTodoReviewRun.started_at), desc(ProjectTodoReviewRun.id))
        .limit(1)
    )


async def latest_project_todo_review_run(
    session: AsyncSession,
    todo_id: UUID,
) -> ProjectTodoReviewRun | None:
    return await session.scalar(
        select(ProjectTodoReviewRun)
        .where(ProjectTodoReviewRun.project_todo_id == todo_id)
        .order_by(desc(ProjectTodoReviewRun.created_at), desc(ProjectTodoReviewRun.id))
        .limit(1)
    )


async def apply_manual_review_status_to_latest_run(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    review_status: str,
    completed_at: datetime | None = None,
) -> None:
    run = await latest_project_todo_review_run(session, todo.id)
    if run is None:
        return
    mapped = {
        "APPROVED": "PASSED",
        "CHANGES_REQUESTED": "CHANGES_REQUESTED",
        "NEEDS_HUMAN_REVIEW": "FAILED",
    }.get(review_status)
    if mapped is None:
        return
    run.status = mapped
    run.completed_at = _aware(completed_at or datetime.now(UTC))
    if review_status == "NEEDS_HUMAN_REVIEW":
        run.last_error = "Human review requested from todo card."


async def mark_running_review_run_completed_without_verdict(
    session: AsyncSession,
    *,
    window_id: UUID,
    completed_at: datetime,
) -> None:
    run = await latest_running_review_run_for_window(session, window_id)
    if run is None:
        return
    run.status = "FAILED"
    run.completed_at = _aware(completed_at)
    run.last_error = "Review window completed without a structured verdict."


def _diff_stat(summary: dict[str, Any], commits: list[dict[str, Any]], files: list[dict[str, Any]]) -> dict[str, Any]:
    additions = sum(_int(file_entry.get("additions")) for file_entry in files)
    deletions = sum(_int(file_entry.get("deletions")) for file_entry in files)
    return {
        "has_changes": bool(summary.get("has_changes")),
        "commit_count": len(commits),
        "file_count": len(files),
        "additions": additions,
        "deletions": deletions,
    }


def _dirty_state(summary: dict[str, Any]) -> str:
    if summary.get("pending_commit"):
        return "dirty"
    if summary:
        return "clean"
    return "unknown"


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
