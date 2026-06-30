from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.contexts.terminal_runtime.application.stale_window_protection import (
    retained_recent_active_tmux_window_ids,
)
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxTarget
from app.model_base import Base
from app.models import Event, EventSourceType, LOCAL_CLIENT_ID, VirtualWindow, WindowStatus


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_retained_recent_active_tmux_window_ids_keeps_latest_50_non_idle_windows(db_session) -> None:
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    active_ids = []
    for index in range(51):
        activity_at = now - timedelta(seconds=index)
        window_id = uuid4()
        event_id = uuid4()
        active_ids.append(window_id)
        db_session.add(
            VirtualWindow(
                id=window_id,
                client_id=client_id,
                title=f"Active {index}",
                status=WindowStatus.active,
                tmux_session="web-terminal",
                tmux_window_id=f"@{index}",
                agent_activity_latest_at=activity_at,
                agent_activity_latest_event_id=event_id,
                created_at=activity_at,
            )
        )
        db_session.add(
            Event(
                id=event_id,
                client_id=client_id,
                source_type=EventSourceType.agent_tool_record,
                source_id=f"codex-session-{index}",
                kind="response_item",
                virtual_window_id=window_id,
                payload_json={
                    "provider": "codex",
                    "raw_type": "response_item",
                    "payload": {"type": "message", "role": "assistant"},
                },
                fingerprint=f"active-window-{index}",
                created_at=activity_at,
            )
        )
        db_session.add(
            Event(
                client_id=client_id,
                source_type=EventSourceType.terminal,
                source_id=str(window_id),
                kind="terminal_input_command",
                virtual_window_id=window_id,
                payload_json={"command": "codex exec 'fix'", "sequence": index},
                fingerprint=f"active-window-command-{index}",
                created_at=activity_at - timedelta(seconds=1),
            )
        )
    idle_id = uuid4()
    db_session.add(
        VirtualWindow(
            id=idle_id,
            client_id=client_id,
            title="Idle",
            status=WindowStatus.active,
            tmux_session="web-terminal",
            tmux_window_id="@idle",
            created_at=now + timedelta(seconds=1),
        )
    )
    await db_session.flush()

    retained = await retained_recent_active_tmux_window_ids(db_session, client_id, now=now)

    assert len(retained) == 50
    assert set(active_ids[:50]) == retained
    assert active_ids[50] not in retained
    assert idle_id not in retained


@pytest.mark.asyncio
async def test_retained_recent_active_tmux_window_ids_includes_remote_windows(db_session) -> None:
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    client_id = uuid4()
    window_id = uuid4()
    event_id = uuid4()
    db_session.add(
        VirtualWindow(
            id=window_id,
            client_id=client_id,
            title="Remote active",
            status=WindowStatus.active,
            remote_session_id="remote-pool",
            remote_window_id="@7",
            agent_activity_latest_at=now,
            agent_activity_latest_event_id=event_id,
            created_at=now,
        )
    )
    db_session.add(
        Event(
            id=event_id,
            client_id=client_id,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session-remote",
            kind="response_item",
            virtual_window_id=window_id,
            payload_json={
                "provider": "codex",
                "raw_type": "response_item",
                "payload": {"type": "message", "role": "assistant"},
            },
            fingerprint="remote-active-window",
            created_at=now,
        )
    )
    db_session.add(
        Event(
            client_id=client_id,
            source_type=EventSourceType.terminal,
            source_id=str(window_id),
            kind="terminal_input_command",
            virtual_window_id=window_id,
            payload_json={"command": "codex exec 'fix remote'", "sequence": 1},
            fingerprint="remote-active-window-command",
            created_at=now - timedelta(seconds=1),
        )
    )
    await db_session.flush()

    retained = await retained_recent_active_tmux_window_ids(db_session, client_id, now=now)

    assert retained == {window_id}


@pytest.mark.asyncio
async def test_local_runtime_factory_retains_recent_active_stale_window(db_session) -> None:
    now = datetime.now(timezone.utc)
    window_id = uuid4()
    event_id = uuid4()
    db_session.add(
        VirtualWindow(
            id=window_id,
            client_id=LOCAL_CLIENT_ID,
            title="Active stale tmux",
            status=WindowStatus.active,
            tmux_session="web-terminal",
            tmux_window_id="@7",
            agent_activity_latest_at=now,
            agent_activity_latest_event_id=event_id,
            created_at=now,
        )
    )
    db_session.add(
        Event(
            id=event_id,
            client_id=LOCAL_CLIENT_ID,
            source_type=EventSourceType.agent_tool_record,
            source_id="codex-session",
            kind="response_item",
            virtual_window_id=window_id,
            payload_json={
                "provider": "codex",
                "raw_type": "response_item",
                "payload": {"type": "message", "role": "assistant"},
            },
            fingerprint="active-stale-window",
            created_at=now,
        )
    )
    db_session.add(
        Event(
            client_id=LOCAL_CLIENT_ID,
            source_type=EventSourceType.terminal,
            source_id=str(window_id),
            kind="terminal_input_command",
            virtual_window_id=window_id,
            payload_json={"command": "codex exec 'fix'", "sequence": 1},
            fingerprint="active-stale-window-command",
            created_at=now - timedelta(seconds=1),
        )
    )
    await db_session.flush()

    class SessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    calls: list[tuple[str, object]] = []

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return True

        async def window_activity_timestamp(self, target: TmuxTarget) -> float:
            calls.append(("window_activity_timestamp", target))
            return 800.0

        async def kill_window(self, target: TmuxTarget) -> None:
            calls.append(("kill_window", target))

        async def recreate_window(self, target: TmuxTarget, *, local_window_id) -> TmuxTarget:
            calls.append(("recreate_window", (target, local_window_id)))
            return target

    runtime = create_local_terminal_runtime(FakeTmuxManager(), session_factory=SessionFactory())
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    ensured = await runtime._ensure_runtime_window(window, local_window_id=window_id)

    assert ensured == window
    assert calls == [
        ("has_window", TmuxTarget(session="web-terminal", window_id="@7")),
        ("window_activity_timestamp", TmuxTarget(session="web-terminal", window_id="@7")),
    ]
