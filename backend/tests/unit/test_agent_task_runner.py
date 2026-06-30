from __future__ import annotations

from uuid import uuid4

import pytest

from tests.unit.test_summary_scheduler_support import db_session  # noqa: F401

from app.contexts.terminal_runtime.application.agent_task_runner import (
    AgentTaskSpec,
    AgentTaskResult,
    run_agent_task,
)


def test_agent_task_spec_defaults() -> None:
    spec = AgentTaskSpec(
        prompt="hello",
        source_window_id=uuid4(),
        is_complete=lambda text: True,
        timeout_seconds=60.0,
        title="test",
    )
    assert spec.output_path is None
    assert spec.derived_context_extras == {}
    assert spec.source_agent_command is None


def test_agent_task_result_carries_output_metadata() -> None:
    result = AgentTaskResult(
        output='{"verdict":"complete"}',
        ephemeral_window_id=uuid4(),
        started_at=__import__("datetime").datetime.now(),
        finished_at=__import__("datetime").datetime.now(),
    )
    assert "verdict" in result.output


@pytest.mark.asyncio
async def test_run_agent_task_raises_when_client_missing(db_session) -> None:
    spec = AgentTaskSpec(
        prompt="hello",
        source_window_id=uuid4(),
        is_complete=lambda text: True,
        timeout_seconds=60.0,
        title="test",
    )
    with pytest.raises(ValueError, match="client not found"):
        await run_agent_task(
            db_session,
            spec,
            client_id=uuid4(),
            session_factory=lambda: None,
            terminal_broker=None,
            tmux_manager=object(),  # type: ignore[arg-type]
            registry=None,
        )
