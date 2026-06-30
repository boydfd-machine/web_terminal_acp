from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import Client, ClientRuntime, ClientStatus, GitWorktreeRun, VirtualWindow, WindowGitBinding
from app.services import git_worktree_coordinator as coordinator


WORKTREE_ROOT = "/repo/.worktrees/test"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_snapshot_refresh_skips_when_window_refresh_lock_is_busy(
    db_session,
    monkeypatch,
) -> None:
    client = Client(
        id=uuid4(),
        name="local",
        token_hash="hash",
        status=ClientStatus.ONLINE,
        runtime=ClientRuntime.local,
    )
    window = VirtualWindow(id=uuid4(), client_id=client.id, title="Terminal")
    binding = WindowGitBinding(
        client_id=client.id,
        virtual_window_id=window.id,
        main_repo_root="/repo",
        worktree_root=WORKTREE_ROOT,
        branch="agent/test",
        discovery_method="osc",
    )
    run = GitWorktreeRun(
        client_id=client.id,
        virtual_window_id=window.id,
        command_sequence="worktree:baseline",
        status="bound",
        worktree_root=WORKTREE_ROOT,
        main_repo_root="/repo",
        start_snapshot_json={"is_linked_worktree": True, "head_sha": "base"},
    )
    db_session.add_all([client, window, binding, run])
    await db_session.flush()

    async def busy_lock(*args, **kwargs):
        return False

    async def unexpected_snapshot(*args, **kwargs):
        raise AssertionError("snapshot refresh should not run while another refresh owns the lock")

    monkeypatch.setattr(coordinator, "try_acquire_window_refresh_lock", busy_lock)
    monkeypatch.setattr(coordinator, "local_git_worktree_action", unexpected_snapshot)

    changed = await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    assert changed is False
    assert run.end_snapshot_json is None
