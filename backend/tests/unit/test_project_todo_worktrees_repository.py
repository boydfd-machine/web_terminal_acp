from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.terminal_runtime.infrastructure.git_worktree_repository import (
    latest_git_worktree_snapshots_by_window_ids,
)
from app.contexts.workspace.infrastructure.project_todo_worktrees_repository import (
    list_project_todo_worktree_attention_targets,
    project_todo_worktree_attention_targets_statement,
    sync_project_todo_worktree_summaries_for_window,
)
from app.model_base import Base
from app.models import (
    Client,
    ClientRuntime,
    ClientStatus,
    GitWorktreeRun,
    ProjectTodo,
    ProjectTodoStatus,
    VirtualWindow,
)


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/worktrees.db")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        await engine.dispose()


def test_project_todo_worktree_attention_targets_query_uses_narrow_columns() -> None:
    statement = project_todo_worktree_attention_targets_statement(limit=50)

    selected_columns = tuple(column.name for column in statement.selected_columns)
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert selected_columns == ("client_id", "assigned_window_id")
    assert "->> 'merge_attention_required'" in compiled
    assert "IN ('unmerged', 'conflict')" in compiled
    assert "IN ('AWAITING_REVIEW', 'DONE')" in compiled
    assert "ORDER BY project_todos.updated_at DESC, project_todos.id DESC" in compiled
    assert "implementation_worktree_json_1" not in compiled
    assert "POSTCOMPILE" not in compiled


@pytest.mark.asyncio
async def test_sync_project_todo_worktree_summary_clears_merge_attention(
    session_factory,
) -> None:
    base_time = datetime.now(timezone.utc)
    async with session_factory() as session:
        client = Client(
            id=uuid4(),
            name="local",
            token_hash="hash",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.local,
        )
        window = VirtualWindow(id=uuid4(), client_id=client.id, title="Todo worker")
        todo = ProjectTodo(
            client_id=client.id,
            project_path="/repo",
            title="Merge status refresh",
            status=ProjectTodoStatus.awaiting_review,
            assigned_window_id=window.id,
            implementation_worktree_json={
                "window_id": str(window.id),
                "worktree_root": "/repo/.worktrees/feature",
                "branch": "agent/feature",
                "merge_status": "unmerged",
                "merged_to_main": False,
                "merge_attention_required": True,
                "captured_at": (base_time - timedelta(minutes=5)).isoformat(),
            },
        )
        stale_agent_run = GitWorktreeRun(
            client_id=client.id,
            virtual_window_id=window.id,
            command_sequence="7",
            status="completed",
            main_repo_root="/repo",
            worktree_root="/repo/.worktrees/feature",
            ended_at=base_time + timedelta(seconds=1),
            end_snapshot_json=_snapshot("unmerged", merged=False),
            session_diff_json={"has_changes": True, "end_head": "feature"},
        )
        refreshed_tracking_run = GitWorktreeRun(
            client_id=client.id,
            virtual_window_id=window.id,
            command_sequence="worktree:feature",
            status="completed",
            main_repo_root="/repo",
            worktree_root="/repo/.worktrees/feature",
            ended_at=base_time + timedelta(seconds=2),
            resolved_at=base_time + timedelta(seconds=2),
            start_snapshot_json={"head_sha": "base"},
            end_snapshot_json=_snapshot("merged", merged=True),
            session_diff_json={
                "has_changes": True,
                "start_head": "base",
                "end_head": "feature",
                "commits": [
                    {
                        "sha": "feature",
                        "short_sha": "feature",
                        "subject": "Implement refresh",
                        "files": [{"path": "backend/app.py", "status": "modified"}],
                    }
                ],
                "files": [{"path": "backend/app.py", "status": "modified"}],
            },
        )
        session.add_all([client, window, todo, stale_agent_run, refreshed_tracking_run])
        await session.flush()

        changed = await sync_project_todo_worktree_summaries_for_window(
            session,
            client.id,
            window.id,
        )

        assert changed is True
        summary = todo.implementation_worktree_json
        assert summary is not None
        assert summary["merge_status"] == "merged"
        assert summary["merged_to_main"] is True
        assert summary["merge_attention_required"] is False
        assert summary["end_head"] == "feature"
        assert summary["commits"][0]["subject"] == "Implement refresh"

        changed_again = await sync_project_todo_worktree_summaries_for_window(
            session,
            client.id,
            window.id,
        )

        assert changed_again is False


@pytest.mark.asyncio
async def test_implementation_worktree_summary_preserves_diff_runs_for_archived_windows(
    session_factory,
) -> None:
    base_time = datetime.now(timezone.utc)
    async with session_factory() as session:
        client = Client(
            id=uuid4(),
            name="local",
            token_hash="hash",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.local,
        )
        window = VirtualWindow(id=uuid4(), client_id=client.id, title="Todo worker")
        run = GitWorktreeRun(
            client_id=client.id,
            virtual_window_id=window.id,
            command_sequence="12",
            agent_provider="codex",
            status="completed",
            main_repo_root="/repo",
            worktree_root="/repo/.worktrees/feature",
            started_at=base_time,
            ended_at=base_time + timedelta(seconds=1),
            start_snapshot_json={"head_sha": "base"},
            end_snapshot_json=_snapshot("merged", merged=True),
            session_diff_json={
                "has_changes": True,
                "start_head": "base",
                "end_head": "feature",
                "commits": [
                    {
                        "sha": "feature",
                        "short_sha": "feature",
                        "subject": "Keep todo diff",
                        "files": [
                            {
                                "path": "backend/app.py",
                                "status": "modified",
                                "additions": 1,
                                "deletions": 1,
                                "patch": "@@ -1 +1 @@\n-old\n+new\n",
                            }
                        ],
                    }
                ],
                "files": [
                    {
                        "path": "backend/app.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "commits": ["feature"],
                    }
                ],
            },
        )
        session.add_all([client, window, run])
        await session.flush()

        from app.contexts.workspace.infrastructure.project_todo_worktrees_repository import (
            implementation_worktree_summary,
        )

        summary = await implementation_worktree_summary(session, window.id)

        assert summary is not None
        diff_runs = summary["diff_runs"]
        assert diff_runs[0]["id"] == str(run.id)
        assert diff_runs[0]["virtual_window_id"] == str(window.id)
        assert diff_runs[0]["run_type"] == "agent"
        assert diff_runs[0]["session_diff_json"]["commits"][0]["files"][0]["patch"] == (
            "@@ -1 +1 @@\n-old\n+new\n"
        )


@pytest.mark.asyncio
async def test_latest_git_worktree_snapshot_uses_recent_refresh_time(session_factory) -> None:
    base_time = datetime.now(timezone.utc)
    async with session_factory() as session:
        client = Client(
            id=uuid4(),
            name="local",
            token_hash="hash",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.local,
        )
        window = VirtualWindow(id=uuid4(), client_id=client.id, title="Todo worker")
        session.add_all([
            client,
            window,
            GitWorktreeRun(
                client_id=client.id,
                virtual_window_id=window.id,
                command_sequence="7",
                status="completed",
                ended_at=base_time + timedelta(seconds=1),
                end_snapshot_json=_snapshot("unmerged", merged=False),
            ),
            GitWorktreeRun(
                client_id=client.id,
                virtual_window_id=window.id,
                command_sequence="worktree:feature",
                status="completed",
                ended_at=base_time + timedelta(seconds=2),
                resolved_at=base_time + timedelta(seconds=2),
                end_snapshot_json=_snapshot("merged", merged=True),
            ),
        ])
        await session.flush()

        snapshots = await latest_git_worktree_snapshots_by_window_ids(session, [window.id])

        assert snapshots[window.id]["merge_status"] == "merged"


@pytest.mark.asyncio
async def test_list_project_todo_worktree_attention_targets_filters_stale_cards(
    session_factory,
) -> None:
    async with session_factory() as session:
        client = Client(
            id=uuid4(),
            name="local",
            token_hash="hash",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.local,
        )
        stale_window = VirtualWindow(id=uuid4(), client_id=client.id, title="Stale")
        merged_window = VirtualWindow(id=uuid4(), client_id=client.id, title="Merged")
        stale_todo = ProjectTodo(
            client_id=client.id,
            project_path="/repo",
            title="Needs merge",
            status=ProjectTodoStatus.awaiting_review,
            assigned_window_id=stale_window.id,
            implementation_worktree_json=_snapshot("unmerged", merged=False),
        )
        merged_todo = ProjectTodo(
            client_id=client.id,
            project_path="/repo",
            title="Already merged",
            status=ProjectTodoStatus.awaiting_review,
            assigned_window_id=merged_window.id,
            implementation_worktree_json=_snapshot("merged", merged=True),
        )
        draft_todo = ProjectTodo(
            client_id=client.id,
            project_path="/repo",
            title="Draft",
            status=ProjectTodoStatus.todo,
            assigned_window_id=stale_window.id,
            implementation_worktree_json=_snapshot("unmerged", merged=False),
        )
        session.add_all([client, stale_window, merged_window, stale_todo, merged_todo, draft_todo])
        await session.flush()

        targets = await list_project_todo_worktree_attention_targets(session)

        assert targets == [(client.id, stale_window.id)]


def _snapshot(status: str, *, merged: bool) -> dict[str, object]:
    return {
        "is_linked_worktree": True,
        "main_repo_root": "/repo",
        "worktree_root": "/repo/.worktrees/feature",
        "branch": "agent/feature",
        "head_sha": "feature",
        "merge_status": status,
        "merge_status_reason": "head_is_ancestor_of_main" if merged else "head_not_merged_to_main",
        "merged_to_main": merged,
        "main_branch": "main",
        "main_head_sha": "feature" if merged else "base",
    }
