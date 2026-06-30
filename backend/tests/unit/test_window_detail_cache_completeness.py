import json

from fastapi import Response

from app.contexts.windows.api.window_lifecycle_routes import _cached_response_incomplete


def _json_response(payload: dict[str, object]) -> Response:
    return Response(content=json.dumps(payload), media_type="application/json")


def test_cached_claude_token_usage_without_limit_is_incomplete() -> None:
    assert _cached_response_incomplete(
        _json_response(
            {
                "shell_command": "claude",
                "agent_token_usage": {
                    "total": {"total_tokens": 113701},
                    "context_window": None,
                    "auto_compact_token_limit": None,
                },
            }
        )
    )


def test_cached_claude_token_usage_with_compact_limit_is_complete() -> None:
    assert not _cached_response_incomplete(
        _json_response(
            {
                "shell_command": "claude",
                "agent_token_usage": {
                    "total": {"total_tokens": 113701},
                    "context_window": None,
                    "auto_compact_token_limit": 230000,
                },
            }
        )
    )


def test_cached_other_agent_token_usage_without_limit_is_complete() -> None:
    assert not _cached_response_incomplete(
        _json_response(
            {
                "shell_command": "cursor-agent",
                "agent_token_usage": {
                    "total": {"total_tokens": 113701},
                    "context_window": None,
                    "auto_compact_token_limit": None,
                },
            }
        )
    )
