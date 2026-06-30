from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.model_base import Base
from app.models import (
    Client,
    ClientRuntime,
    ClientStatus,
    Event,
    EventSourceType,
    GitWorktreeRun,
    VirtualWindow,
    WindowGitBinding,
)
from app.services import git_worktree_coordinator as coordinator
from app.contexts.windows.api.window_git_runs_routes import _git_worktree_runs_need_refresh

WORKTREE_ROOT = "/repo/.web-terminal-acp/worktrees/window-1"
MAIN_REPO_ROOT = "/repo"
LANDED_SHA = "abc1234"


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


def _merged_snapshot(head: str = "base") -> dict[str, object]:
    return {
        "is_linked_worktree": True,
        "worktree_root": WORKTREE_ROOT,
        "main_repo_root": MAIN_REPO_ROOT,
        "branch": "agent/rabbit-favicon",
        "head_sha": head,
        "status_porcelain": "",
        "diff_stat": "",
        "staged_diff_stat": "",
        "commits": [],
        "merge_status": "merged",
        "merge_status_reason": "head_is_ancestor_of_main",
        "merged_to_main": True,
        "main_branch": "main",
        "main_head_sha": head,
        "main_merge_in_progress": False,
        "unmerged_files": [],
    }


@pytest.mark.asyncio
async def test_refresh_recovers_empty_merged_tracking_diff_from_landed_commit_event(
    db_session,
    monkeypatch,
) -> None:
    client, window = await _add_window(db_session)
    db_session.add(
        WindowGitBinding(
            client_id=client.id,
            virtual_window_id=window.id,
            main_repo_root=MAIN_REPO_ROOT,
            worktree_root=WORKTREE_ROOT,
            branch="agent/rabbit-favicon",
            discovery_method="osc",
        )
    )
    run = GitWorktreeRun(
        client_id=client.id,
        virtual_window_id=window.id,
        command_sequence="worktree:window1",
        status="completed",
        main_repo_root=MAIN_REPO_ROOT,
        worktree_root=WORKTREE_ROOT,
        discovery_method="osc",
        start_snapshot_json=_merged_snapshot(),
        end_snapshot_json=_merged_snapshot(),
        session_diff_json={
            "has_changes": False,
            "head_moved": False,
            "start_head": "base",
            "end_head": "base",
            "commits": [],
            "files": [],
        },
    )
    db_session.add(run)
    db_session.add(
        Event(
            client_id=client.id,
            source_type=EventSourceType.agent_tool_record,
            source_id="claude-session",
            kind="assistant_message",
            virtual_window_id=window.id,
            payload_json={
                "provider": "claude_code",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"merged to main with commit `{LANDED_SHA}`",
                        }
                    ]
                },
            },
            fingerprint=f"agent_tool_record:{window.id}:landed-commit",
        )
    )
    await db_session.flush()

    async def fake_action(action: str, **payload):
        if action != "snapshot":
            return None
        if payload["worktree_root"] == MAIN_REPO_ROOT:
            assert payload["base_head"] == "base"
            assert payload["known_head_sha"] == LANDED_SHA
            return {
                "ok": True,
                "snapshot": {
                    **_merged_snapshot(head=LANDED_SHA),
                    "is_linked_worktree": False,
                    "worktree_root": MAIN_REPO_ROOT,
                    "commits": [
                        {
                            "sha": LANDED_SHA,
                            "short_sha": LANDED_SHA,
                            "subject": "Replace robot favicon with rabbit",
                            "author_name": "Open Claw",
                            "author_email": "open@example.com",
                            "authored_at": "2026-06-29T06:20:00+00:00",
                            "files": [
                                {
                                    "path": "frontend/index.html",
                                    "old_path": None,
                                    "status": "modified",
                                    "additions": 1,
                                    "deletions": 1,
                                    "patch": "@@ -1 +1 @@\n-/robot.svg\n+/rabbit.svg\n",
                                }
                            ],
                        }
                    ],
                },
            }
        return {"ok": True, "snapshot": _merged_snapshot()}

    monkeypatch.setattr(coordinator, "local_git_worktree_action", fake_action)

    changed = await coordinator.process_git_worktree_snapshot_refresh(
        db_session,
        client_id=client.id,
        window_id=window.id,
        registry=None,
        client_runtime=ClientRuntime.local,
    )

    assert changed is True
    assert run.session_diff_json["has_changes"] is True
    assert run.session_diff_json["commits"][0]["sha"] == LANDED_SHA
    assert run.session_diff_json["commits"][0]["files"][0]["path"] == "frontend/index.html"
    assert run.session_diff_json["files"] == [
        {
            "path": "frontend/index.html",
            "old_path": None,
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "commits": [LANDED_SHA],
        }
    ]


def test_git_runs_api_refreshes_empty_merged_tracking_diff() -> None:
    run = GitWorktreeRun(
        client_id=uuid4(),
        virtual_window_id=uuid4(),
        command_sequence="worktree:window1",
        status="completed",
        start_snapshot_json=_merged_snapshot(),
        end_snapshot_json=_merged_snapshot(),
        session_diff_json={
            "has_changes": False,
            "commits": [],
            "files": [],
        },
    )

    assert _git_worktree_runs_need_refresh([run]) is True
