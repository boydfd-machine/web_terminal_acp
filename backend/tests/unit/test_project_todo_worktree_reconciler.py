from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.terminal_runtime.application import git_worktree_coordinator as coordinator
from app.contexts.workspace.application import project_todo_worktree_reconciler as reconciler
from app.model_base import Base
from app.models import (
    Client,
    ClientRuntime,
    ClientStatus,
    GitWorktreeRun,
    ProjectTodo,
    ProjectTodoStatus,
    VirtualWindow,
    WindowGitBinding,
)


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/reconciler.db")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconciler_refreshes_stale_project_todo_merge_attention(
    session_factory,
    monkeypatch,
) -> None:
    client_id = uuid4()
    window_id = uuid4()
    async with session_factory() as session:
        client = Client(
            id=client_id,
            name="local",
            token_hash="hash",
            status=ClientStatus.ONLINE,
            runtime=ClientRuntime.local,
        )
        window = VirtualWindow(id=window_id, client_id=client_id, title="Todo worker")
        todo = ProjectTodo(
            client_id=client_id,
            project_path="/repo",
            title="Merge status refresh",
            status=ProjectTodoStatus.awaiting_review,
            assigned_window_id=window_id,
            implementation_worktree_json=_snapshot("unmerged", merged=False),
        )
        binding = WindowGitBinding(
            client_id=client_id,
            virtual_window_id=window_id,
            main_repo_root="/repo",
            worktree_root="/repo/.worktrees/feature",
            branch="agent/feature",
            discovery_method="osc",
        )
        run = GitWorktreeRun(
            client_id=client_id,
            virtual_window_id=window_id,
            command_sequence="worktree:feature",
            status="completed",
            main_repo_root="/repo",
            worktree_root="/repo/.worktrees/feature",
            discovery_method="osc",
            start_snapshot_json=_snapshot("unmerged", merged=False),
            end_snapshot_json=_snapshot("unmerged", merged=False),
            session_diff_json={"has_changes": True, "merge_status": "unmerged"},
            resolved_at=None,
            ended_at=datetime.now(timezone.utc),
        )
        session.add_all([client, window, todo, binding, run])
        await session.commit()

    monkeypatch.setattr(coordinator, "local_git_worktree_action", _fake_merged_action)
    events = _FakeUiEventHub()

    processed = await reconciler.process_project_todo_worktree_reconciliation_once(
        session_factory,
        registry=None,
        ui_event_hub=events,
    )

    assert processed == 1
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo.id)
        run = await session.get(GitWorktreeRun, run.id)
        assert todo is not None
        assert run is not None
        assert todo.implementation_worktree_json["merge_status"] == "merged"
        assert todo.implementation_worktree_json["merge_attention_required"] is False
        assert run.end_snapshot_json["merge_status"] == "merged"
        assert run.resolved_at is not None
    assert events.invalidations == [
        {
            "resources": ["window", "tree", "git_runs", "project_todos"],
            "client_id": client_id,
            "window_id": window_id,
            "reason": "git_worktree_reconciled",
        }
    ]


async def _fake_merged_action(action: str, **payload):
    if action != "snapshot":
        return None
    return {
        "ok": True,
        "snapshot": _snapshot("merged", merged=True),
    }


def _snapshot(status: str, *, merged: bool) -> dict[str, object]:
    return {
        "is_linked_worktree": True,
        "main_repo_root": "/repo",
        "worktree_root": "/repo/.worktrees/feature",
        "branch": "agent/feature",
        "head_sha": "feature",
        "status_porcelain": "",
        "diff_stat": "",
        "staged_diff_stat": "",
        "commits": [],
        "merge_status": status,
        "merge_status_reason": "head_is_ancestor_of_main" if merged else "head_not_merged_to_main",
        "merged_to_main": merged,
        "main_branch": "main",
        "main_head_sha": "feature" if merged else "base",
    }


class _FakeUiEventHub:
    def __init__(self) -> None:
        self.invalidations: list[dict[str, object]] = []

    async def publish_invalidation(self, resources, *, client_id=None, window_id=None, reason=None) -> None:
        self.invalidations.append(
            {
                "resources": list(resources),
                "client_id": client_id,
                "window_id": window_id,
                "reason": reason,
            }
        )
