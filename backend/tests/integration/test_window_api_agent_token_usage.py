import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.models import Event, EventSourceType
from tests.integration.test_window_api_support import *  # noqa: F403


@pytest.mark.asyncio
async def test_get_window_returns_claude_code_agent_token_usage(db_client):
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "claude"},
    )
    window_id = UUID(create_response.json()["id"])
    used_at = datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session",
                kind="assistant",
                virtual_window_id=window_id,
                payload_json={
                    "provider": "claude_code",
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "done"}],
                        "usage": {
                            "input_tokens": 9370,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 13824,
                            "output_tokens": 19,
                        },
                    },
                },
                fingerprint=f"test-claude-token-usage:{window_id}",
                created_at=used_at,
            )
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    usage = response.json()["agent_token_usage"]
    assert usage["context"]["total_tokens"] == 23213
    assert usage["total"]["total_tokens"] == 23213
    assert usage["total"]["input_tokens"] == 9370
    assert usage["total"]["cached_input_tokens"] == 13824
    assert usage["total"]["output_tokens"] == 19
    assert usage["providers"] == ["claude_code"]
    assert usage["event_count"] == 1


@pytest.mark.asyncio
async def test_get_window_fills_claude_compact_limit_from_window_config(
    db_client,
    tmp_path,
    monkeypatch,
):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    client_id = await get_local_client_id(db_client)
    create_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "claude"},
    )
    window_id = UUID(create_response.json()["id"])
    claude_home = home / ".web-terminal-acp" / "claude-code-homes" / str(window_id)
    claude_home.mkdir(parents=True, exist_ok=True)
    (claude_home / "settings.json").write_text(
        json.dumps({"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "230000"}}),
        encoding="utf-8",
    )

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                source_type=EventSourceType.agent_tool_record,
                source_id="claude-session",
                kind="assistant",
                virtual_window_id=window_id,
                payload_json={
                    "provider": "claude_code",
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input_tokens": 112838,
                            "output_tokens": 863,
                        },
                    },
                },
                fingerprint=f"test-claude-compact-limit:{window_id}",
                created_at=datetime(2026, 6, 9, 14, 46, tzinfo=timezone.utc),
            )
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert response.status_code == 200
    usage = response.json()["agent_token_usage"]
    assert usage["context"]["total_tokens"] == 113701
    assert usage["auto_compact_token_limit"] == 230000
