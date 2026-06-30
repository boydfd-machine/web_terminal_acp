from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.project_todo_review_schemas import (
    ProjectTodoReviewRunListOut,
    ProjectTodoReviewRunOut,
    ProjectTodoReviewTargetListOut,
    ProjectTodoReviewTargetOut,
    ProjectTodoWorkSnapshotListOut,
    ProjectTodoWorkSnapshotOut,
)
from app.contexts.workspace.application.project_files import ProjectPathError, resolve_project_relative_path
from app.contexts.workspace.application.project_todo_reviews import (
    create_local_review_target,
    create_project_todo_work_snapshot,
    latest_project_todo_work_snapshot,
    list_project_todo_review_runs,
    list_project_todo_review_targets,
    list_project_todo_work_snapshots,
)
from app.contexts.workspace.application.project_todo_repository import get_project_todo
from app.db import get_session
from app.models import (
    Client,
    ProjectTodo,
    ProjectTodoReviewRun,
    ProjectTodoReviewTarget,
    ProjectTodoWorkSnapshot,
)

router = APIRouter(prefix="/api/clients/{client_id}/projects/todos", tags=["project_todo_reviews"])


@router.get("/{todo_id}/work-snapshots", response_model=ProjectTodoWorkSnapshotListOut)
async def read_todo_work_snapshots(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoWorkSnapshotListOut:
    await _require_todo(session, client_id, project_path, todo_id)
    snapshots = await list_project_todo_work_snapshots(session, todo_id)
    return ProjectTodoWorkSnapshotListOut(work_snapshots=[_snapshot_out(snapshot) for snapshot in snapshots])


@router.get("/{todo_id}/review-targets", response_model=ProjectTodoReviewTargetListOut)
async def read_todo_review_targets(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoReviewTargetListOut:
    await _require_todo(session, client_id, project_path, todo_id)
    targets = await list_project_todo_review_targets(session, todo_id)
    return ProjectTodoReviewTargetListOut(review_targets=[_target_out(target) for target in targets])


@router.post("/{todo_id}/review-targets", response_model=ProjectTodoReviewTargetOut)
async def create_todo_review_target(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoReviewTargetOut:
    todo = await _require_todo(session, client_id, project_path, todo_id)
    snapshot = await latest_project_todo_work_snapshot(session, todo_id)
    if snapshot is None:
        snapshot = await create_project_todo_work_snapshot(
            session,
            todo,
            role="implementation",
            window_id=todo.assigned_window_id,
            worktree_summary=todo.implementation_worktree_json,
        )
    target = await create_local_review_target(session, todo, snapshot)
    await session.commit()
    await session.refresh(target)
    return _target_out(target)


@router.get("/{todo_id}/review-runs", response_model=ProjectTodoReviewRunListOut)
async def read_todo_review_runs(
    client_id: UUID,
    todo_id: UUID,
    project_path: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectTodoReviewRunListOut:
    await _require_todo(session, client_id, project_path, todo_id)
    runs = await list_project_todo_review_runs(session, todo_id)
    return ProjectTodoReviewRunListOut(review_runs=[_run_out(run) for run in runs])


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


async def _require_todo(session: AsyncSession, client_id: UUID, project_path: str, todo_id: UUID) -> ProjectTodo:
    await _require_client(session, client_id)
    todo = await get_project_todo(session, client_id, _normalize_project_path(project_path), todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo not found")
    return todo


def _normalize_project_path(project_path: str) -> str:
    try:
        return resolve_project_relative_path(project_path).project_path
    except ProjectPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _snapshot_out(snapshot: ProjectTodoWorkSnapshot) -> ProjectTodoWorkSnapshotOut:
    return ProjectTodoWorkSnapshotOut(
        id=snapshot.id,
        todo_id=snapshot.project_todo_id,
        client_id=snapshot.client_id,
        project_path=snapshot.project_path,
        window_id=snapshot.window_id,
        role=snapshot.role,
        branch_name=snapshot.branch_name,
        base_ref=snapshot.base_ref,
        base_sha=snapshot.base_sha,
        head_sha=snapshot.head_sha,
        commit_shas=snapshot.commit_shas_json or [],
        diff_stat=snapshot.diff_stat_json,
        changed_files=snapshot.changed_files_json or [],
        dirty_state=snapshot.dirty_state,
        captured_at=snapshot.captured_at,
    )


def _target_out(target: ProjectTodoReviewTarget) -> ProjectTodoReviewTargetOut:
    return ProjectTodoReviewTargetOut(
        id=target.id,
        todo_id=target.project_todo_id,
        work_snapshot_id=target.work_snapshot_id,
        provider=target.provider,
        external_id=target.external_id,
        url=target.url,
        status=target.status,
        base_sha=target.base_sha,
        head_sha=target.head_sha,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _run_out(run: ProjectTodoReviewRun) -> ProjectTodoReviewRunOut:
    return ProjectTodoReviewRunOut(
        id=run.id,
        todo_id=run.project_todo_id,
        review_target_id=run.review_target_id,
        review_window_id=run.review_window_id,
        agent_client=run.agent_client,
        agent_profile_id=run.agent_profile_id,
        status=run.status,
        summary=run.summary,
        findings=run.findings_json or [],
        test_commands=run.test_commands_json or [],
        started_at=run.started_at,
        completed_at=run.completed_at,
        last_error=run.last_error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
