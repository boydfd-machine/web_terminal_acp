import asyncio
from uuid import UUID

import pytest

from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.stale_window_cleanup import ClientStaleWindowCleanup

CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")


def _window(index: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_active_limit_even_when_windows_are_expired() -> None:
    now = 1_000.0
    killed: list[UUID] = []
    cleanup = ClientStaleWindowCleanup(
        cleanup_seconds=100,
        retain_recent_limit=2,
        clock=lambda: now,
        kill_window=lambda window_id: killed.append(window_id),
    )
    old = _window(1)
    retained = _window(2)
    newest = _window(3)

    cleanup.register_window(old, ClientRuntimeWindow("pool", "@1"), activity_at=700.0)
    cleanup.register_window(retained, ClientRuntimeWindow("pool", "@2"), activity_at=800.0)
    cleanup.register_window(newest, ClientRuntimeWindow("pool", "@3"), activity_at=900.0)

    await cleanup.drain_expired()

    assert killed == [old]
    assert cleanup.is_registered(old) is False
    assert cleanup.is_registered(retained) is True
    assert cleanup.is_registered(newest) is True


@pytest.mark.asyncio
async def test_cleanup_reschedules_touched_window_without_scanning_on_touch() -> None:
    now = 100.0
    killed: list[UUID] = []
    cleanup = ClientStaleWindowCleanup(
        cleanup_seconds=10,
        retain_recent_limit=0,
        clock=lambda: now,
        kill_window=lambda window_id: killed.append(window_id),
    )
    window_id = _window(1)

    cleanup.register_window(window_id, ClientRuntimeWindow("pool", "@1"), activity_at=90.0)
    cleanup.touch_window(window_id, activity_at=99.0)

    await cleanup.drain_expired()

    assert killed == []
    assert cleanup.next_delay() == pytest.approx(9.0)

    now = 109.0
    await cleanup.drain_expired()

    assert killed == [window_id]


@pytest.mark.asyncio
async def test_cleanup_does_not_kill_attached_window() -> None:
    killed: list[UUID] = []
    cleanup = ClientStaleWindowCleanup(
        cleanup_seconds=10,
        retain_recent_limit=0,
        clock=lambda: 100.0,
        kill_window=lambda window_id: killed.append(window_id),
    )
    window_id = _window(1)

    cleanup.register_window(window_id, ClientRuntimeWindow("pool", "@1"), activity_at=0.0)
    cleanup.attach_view(window_id)
    await cleanup.drain_expired()

    assert killed == []
    assert cleanup.is_registered(window_id) is True

    cleanup.detach_view(window_id)
    await cleanup.drain_expired()

    assert killed == [window_id]


@pytest.mark.asyncio
async def test_cleanup_requires_matching_detach_for_each_attached_view() -> None:
    killed: list[UUID] = []
    cleanup = ClientStaleWindowCleanup(
        cleanup_seconds=10,
        retain_recent_limit=0,
        clock=lambda: 100.0,
        kill_window=lambda window_id: killed.append(window_id),
    )
    window_id = _window(1)

    cleanup.register_window(window_id, ClientRuntimeWindow("pool", "@1"), activity_at=0.0)
    cleanup.attach_view(window_id)
    cleanup.attach_view(window_id)
    cleanup.detach_view(window_id)
    await cleanup.drain_expired()

    assert killed == []

    cleanup.detach_view(window_id)
    await cleanup.drain_expired()

    assert killed == [window_id]


@pytest.mark.asyncio
async def test_cleanup_loop_uses_deadline_delay_without_busy_polling() -> None:
    now = 100.0
    woke = asyncio.Event()

    cleanup = ClientStaleWindowCleanup(
        cleanup_seconds=60,
        clock=lambda: now,
        kill_window=lambda _window_id: None,
        sleep=lambda _seconds: woke.wait(),
    )
    cleanup.register_window(_window(1), ClientRuntimeWindow("pool", "@1"), activity_at=90.0)

    task = cleanup.start()
    await asyncio.sleep(0)

    assert task is cleanup._task
    assert cleanup.next_delay() == pytest.approx(50.0)

    cleanup.close()
    woke.set()
    with pytest.raises(asyncio.CancelledError):
        await task
