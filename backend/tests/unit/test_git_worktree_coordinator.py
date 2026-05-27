from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
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


async def _add_window(session: AsyncSession) -> tuple[Client, VirtualWindow]:
    client = Client(
        id=uuid4(),
        name="local",
        token_hash="hash",
        status=ClientStatus.ONLINE,
        runtime=ClientRuntime.local,
    )
    window = VirtualWindow(id=uuid4(), client_id=client.id, title="Terminal")
    session.add_all([client, window])
    await session.flush()
    return client, window


def _snapshot(
    worktree_root: str,
    *,
    status: str = "",
    diff: str = "",
    head: str = "aaa",
    commits: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "is_linked_worktree": True,
        "worktree_root": worktree_root,
        "main_repo_root": "/repo",
        "branch": "agent/test",
        "head_sha": head,
        "status_porcelain": status,
        "diff_stat": diff,
        "staged_diff_stat": "",
        "commits": commits or [],
    }


def _fake_action(
    *,
    status: str = "",
    diff: str = "",
    head: str = "aaa",
    commits: list[dict[str, object]] | None = None,
):
    async def fake_action(action: str, **payload):
        if action == "detect":
            return {
                "ok": True,
                "context": {
                    "is_linked_worktree": True,
                    "worktree_root": WORKTREE_ROOT,
                    "main_repo_root": "/repo",
                    "branch": "agent/test",
                },
            }
        if action == "snapshot":
            return {
                "ok": True,
                "snapshot": _snapshot(
                    payload["worktree_root"],
                    status=status,
                    diff=diff,
                    head=head,
                    commits=commits,
                ),
            }
        return None

    return fake_action


async def _add_binding(session: AsyncSession, client: Client, window: VirtualWindow) -> None:
    session.add(
        WindowGitBinding(
            client_id=client.id,
            virtual_window_id=window.id,
            main_repo_root="/repo",
            worktree_root=WORKTREE_ROOT,
            branch="agent/test",
            discovery_method="osc",
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_worktree_registration_persists_binding_and_baseline_run(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)
    monkeypatch.setattr(coordinator, "local_git_worktree_action", _fake_action())

    await coordinator.process_worktree_registration(
        db_session,
        client_id=client.id,
        window_id=window.id,
        marker={"worktree_root": WORKTREE_ROOT, "branch": "agent/test"},
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    binding = await db_session.scalar(select(WindowGitBinding))
    runs = list(await db_session.scalars(select(GitWorktreeRun)))
    assert binding is not None
    assert binding.worktree_root == WORKTREE_ROOT
    assert binding.main_repo_root == "/repo"
    assert len(runs) == 1
    assert runs[0].command_sequence.startswith("worktree:")
    assert runs[0].start_snapshot_json is None


@pytest.mark.asyncio
async def test_git_worktree_add_command_binds_even_when_not_agent_command(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)
    monkeypatch.setattr(coordinator, "local_git_worktree_action", _fake_action())

    await coordinator.process_terminal_commands_for_git(
        db_session,
        client_id=client.id,
        window_id=window.id,
        commands=[{
            "phase": "started",
            "command": "git worktree add ../feature",
            "cwd": "/repo",
            "sequence": 3,
        }],
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    binding = await db_session.scalar(select(WindowGitBinding))
    run = await db_session.scalar(select(GitWorktreeRun))
    assert binding is not None
    assert binding.worktree_root == "/feature"
    assert run is not None
    assert run.command_sequence.startswith("worktree:")


@pytest.mark.asyncio
async def test_git_worktree_add_finished_binds_after_worktree_exists(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)

    async def fake_action(action: str, **payload):
        if action == "detect":
            assert payload["path"] == "/repo"
            return {
                "ok": True,
                "context": {
                    "is_git": True,
                    "is_linked_worktree": False,
                    "worktree_root": "/repo",
                    "main_repo_root": "/repo",
                    "branch": "main",
                },
            }
        return None

    monkeypatch.setattr(coordinator, "local_git_worktree_action", fake_action)

    await coordinator.process_terminal_commands_for_git(
        db_session,
        client_id=client.id,
        window_id=window.id,
        commands=[{
            "phase": "finished",
            "command": "git worktree add ../feature",
            "cwd": "/repo",
            "sequence": 3,
            "exit_status": 0,
        }],
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    binding = await db_session.scalar(select(WindowGitBinding))
    run = await db_session.scalar(select(GitWorktreeRun))
    assert binding is not None
    assert binding.main_repo_root == "/repo"
    assert binding.worktree_root == "/feature"
    assert run is not None
    assert run.command_sequence.startswith("worktree:")


@pytest.mark.asyncio
async def test_failed_git_worktree_add_finished_does_not_bind(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)
    monkeypatch.setattr(coordinator, "local_git_worktree_action", _fake_action())

    await coordinator.process_terminal_commands_for_git(
        db_session,
        client_id=client.id,
        window_id=window.id,
        commands=[{
            "phase": "finished",
            "command": "git worktree add ../feature",
            "cwd": "/repo",
            "sequence": 3,
            "exit_status": 128,
        }],
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    assert await db_session.scalar(select(WindowGitBinding)) is None
    assert await db_session.scalar(select(GitWorktreeRun)) is None


def test_command_tracking_filter_ignores_plain_shell_commands() -> None:
    assert coordinator.commands_need_git_worktree_tracking([
        {"phase": "started", "command": "echo hello", "cwd": "/repo", "sequence": 1},
        {"phase": "finished", "command": "echo hello", "cwd": "/repo", "sequence": 1},
    ]) is False
    assert coordinator.commands_need_git_worktree_tracking([
        {"phase": "started", "command": "git worktree add ../feature", "cwd": "/repo", "sequence": 2},
    ]) is True
    assert coordinator.commands_need_git_worktree_tracking([
        {"phase": "finished", "command": "git worktree add ../feature", "cwd": "/repo", "sequence": 2},
    ]) is True
    assert coordinator.git_worktree_agent_run_sequences([
        {"phase": "started", "command": "echo hello", "cwd": "/repo", "sequence": 1},
        {"phase": "started", "command": "git worktree add ../feature", "cwd": "/repo", "sequence": 2},
        {"phase": "started", "command": "codex exec fix", "cwd": "/repo", "sequence": 3},
    ]) == {"3"}


def test_local_project_worktree_fallback_is_scoped_to_project_worktrees(tmp_path) -> None:
    repo = tmp_path / "repo"
    worktree = repo / ".web-terminal-acp" / "worktrees" / "window-1"
    outside = tmp_path / "outside"
    worktree.mkdir(parents=True)
    outside.mkdir()
    (worktree / ".git").write_text("gitdir: /tmp/repo/.git/worktrees/window-1", encoding="utf-8")
    (outside / ".git").write_text("gitdir: /tmp/repo/.git/worktrees/outside", encoding="utf-8")

    assert coordinator._is_local_project_worktree_path(  # noqa: SLF001
        str(worktree),
        str(repo),
    ) is True
    assert coordinator._is_local_project_worktree_path(  # noqa: SLF001
        str(outside),
        str(repo),
    ) is False


@pytest.mark.asyncio
async def test_agent_command_refresh_records_that_run_diff(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)
    await _add_binding(db_session, client, window)
    monkeypatch.setattr(coordinator, "local_git_worktree_action", _fake_action())
    started = {"phase": "started", "command": "codex exec fix", "cwd": WORKTREE_ROOT, "sequence": 9}

    await coordinator.process_terminal_commands_for_git(
        db_session,
        client_id=client.id,
        window_id=window.id,
        commands=[started],
        registry=None,
        client_runtime=ClientRuntime.local,
    )
    run = await db_session.scalar(select(GitWorktreeRun).where(GitWorktreeRun.command_sequence == "9"))
    assert run is not None
    assert run.status == "bound"

    monkeypatch.setattr(
        coordinator,
        "local_git_worktree_action",
        _fake_action(status=" M file.txt", diff=" file.txt | 1 +"),
    )
    await coordinator.process_terminal_commands_for_git(
        db_session,
        client_id=client.id,
        window_id=window.id,
        commands=[{**started, "phase": "finished"}],
        registry=None,
        client_runtime=ClientRuntime.local,
    )
    await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
        command_sequences={"9"},
    )

    assert run.status == "completed"
    assert run.session_diff_json["end_status_porcelain"] == " M file.txt"
    assert run.pending_commit is True


@pytest.mark.asyncio
async def test_git_worktree_refresh_records_diff_from_persisted_baseline(db_session, monkeypatch) -> None:
    client, window = await _add_window(db_session)
    run = GitWorktreeRun(
        client_id=client.id,
        virtual_window_id=window.id,
        command_sequence="worktree:baseline",
        status="bound",
        worktree_root=WORKTREE_ROOT,
        main_repo_root="/repo",
        start_snapshot_json=_snapshot(WORKTREE_ROOT),
    )
    await _add_binding(db_session, client, window)
    db_session.add(run)
    await db_session.flush()
    monkeypatch.setattr(
        coordinator,
        "local_git_worktree_action",
        _fake_action(status=" M file.txt", diff=" file.txt | 1 +"),
    )

    changed = await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    refreshed = await db_session.get(GitWorktreeRun, run.id)
    assert changed is True
    assert refreshed is not None
    assert refreshed.session_diff_json["has_changes"] is True
    assert refreshed.session_diff_json["end_status_porcelain"] == " M file.txt"
    assert refreshed.pending_commit is True


@pytest.mark.asyncio
async def test_git_worktree_refresh_persists_commit_file_diff_from_baseline(
    db_session,
    monkeypatch,
) -> None:
    client, window = await _add_window(db_session)
    await _add_binding(db_session, client, window)
    run = GitWorktreeRun(
        client_id=client.id,
        virtual_window_id=window.id,
        command_sequence="worktree:baseline",
        status="bound",
        worktree_root=WORKTREE_ROOT,
        main_repo_root="/repo",
        start_snapshot_json=_snapshot(WORKTREE_ROOT, head="base"),
    )
    db_session.add(run)
    await db_session.flush()
    commits = [
        {
            "sha": "feature",
            "short_sha": "feature",
            "subject": "Fix terminal reload autofocus reconnect",
            "author_name": "Open Claw",
            "author_email": "open@example.com",
            "authored_at": "2026-05-27T05:55:00+00:00",
            "files": [
                {
                    "path": "frontend/src/components/TerminalPane.tsx",
                    "old_path": None,
                    "status": "modified",
                    "additions": 12,
                    "deletions": 4,
                    "patch": "@@ -1 +1 @@\n-old\n+new\n",
                }
            ],
        }
    ]
    monkeypatch.setattr(
        coordinator,
        "local_git_worktree_action",
        _fake_action(head="feature", commits=commits),
    )

    await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    refreshed = await db_session.get(GitWorktreeRun, run.id)
    assert refreshed is not None
    assert refreshed.session_diff_json["head_moved"] is True
    assert refreshed.session_diff_json["start_head"] == "base"
    assert refreshed.session_diff_json["end_head"] == "feature"
    assert refreshed.session_diff_json["commits"] == commits
    assert refreshed.session_diff_json["files"] == [
        {
            "path": "frontend/src/components/TerminalPane.tsx",
            "old_path": None,
            "status": "modified",
            "additions": 12,
            "deletions": 4,
            "commits": ["feature"],
        }
    ]


@pytest.mark.asyncio
async def test_git_worktree_refresh_does_not_rewind_completed_tracking_status(
    db_session,
    monkeypatch,
) -> None:
    client, window = await _add_window(db_session)
    await _add_binding(db_session, client, window)
    run = GitWorktreeRun(
        client_id=client.id,
        virtual_window_id=window.id,
        command_sequence="worktree:baseline",
        status="completed",
        worktree_root=WORKTREE_ROOT,
        main_repo_root="/repo",
        start_snapshot_json=_snapshot(WORKTREE_ROOT, head="base"),
    )
    db_session.add(run)
    await db_session.flush()
    monkeypatch.setattr(
        coordinator,
        "local_git_worktree_action",
        _fake_action(head="feature"),
    )

    await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    assert run.status == "completed"
