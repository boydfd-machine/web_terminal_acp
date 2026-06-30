from uuid import uuid4

import pytest

from app.contexts.activity.application import agent_work_status_cache
from app.contexts.activity.application.terminal_work_status import TerminalWorkStatus


@pytest.mark.asyncio
async def test_cached_agent_work_statuses_reloads_after_ttl(monkeypatch) -> None:
    client_id = uuid4()
    window_id = uuid4()
    calls = 0
    now = 100.0

    async def fake_load_projected_work_statuses(_session, _client_id, _window_ids):
        nonlocal calls
        calls += 1
        return {
            window_id: TerminalWorkStatus(
                state=f"STATE_{calls}",
                label=f"State {calls}",
                color="gray",
            )
        }

    monkeypatch.setattr(agent_work_status_cache, "load_projected_work_statuses", fake_load_projected_work_statuses)
    monkeypatch.setattr(agent_work_status_cache, "monotonic", lambda: now)
    monkeypatch.setattr(agent_work_status_cache, "AGENT_WORK_STATUS_CACHE_TTL_SECONDS", 5.0)
    agent_work_status_cache.clear_agent_work_status_cache()

    first = await agent_work_status_cache.cached_agent_work_statuses(None, client_id, [window_id])
    second = await agent_work_status_cache.cached_agent_work_statuses(None, client_id, [window_id])
    now = 106.0
    third = await agent_work_status_cache.cached_agent_work_statuses(None, client_id, [window_id])

    assert first[window_id].state == "STATE_1"
    assert second[window_id].state == "STATE_1"
    assert third[window_id].state == "STATE_2"
    assert calls == 2
    agent_work_status_cache.clear_agent_work_status_cache()
