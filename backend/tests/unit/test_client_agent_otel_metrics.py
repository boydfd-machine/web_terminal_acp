from __future__ import annotations

import asyncio
import json
from uuid import UUID

import pytest

from app.client_agent.otel_metrics import (
    ClaudeCodeOtelMetricsReceiver,
    managed_events_from_claude_code_otlp_metrics,
)


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")


def _attribute(key: str, value: str) -> dict[str, object]:
    return {"key": key, "value": {"stringValue": value}}


def _otlp_token_metrics_payload() -> dict[str, object]:
    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        _attribute("web_terminal.client_id", str(CLIENT_ID)),
                        _attribute("web_terminal.window_id", str(WINDOW_ID)),
                    ]
                },
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "claude_code.token.usage",
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "attributes": [
                                                _attribute("type", token_type),
                                                _attribute("session.id", "claude-session-1"),
                                                _attribute("model", "claude-sonnet-4-6"),
                                            ],
                                            "asInt": str(value),
                                        }
                                        for token_type, value in (
                                            ("input", 9370),
                                            ("cacheRead", 13824),
                                            ("cacheCreation", 7),
                                            ("output", 19),
                                        )
                                    ]
                                },
                            }
                        ]
                    }
                ],
            }
        ]
    }


def test_managed_events_from_claude_code_otlp_metrics_groups_token_usage_by_request() -> None:
    events = managed_events_from_claude_code_otlp_metrics(
        _otlp_token_metrics_payload(),
        client_id=CLIENT_ID,
    )

    assert len(events) == 1
    event = events[0]
    assert event.provider == "claude_code"
    assert event.client_id == CLIENT_ID
    assert event.window_id == WINDOW_ID
    assert event.source_path == "otel://claude-code/metrics"
    assert event.payload["type"] == "otel_metric"
    assert event.payload["name"] == "claude_code.token.usage"
    assert event.payload["WEB_TERMINAL_CLIENT_ID"] == str(CLIENT_ID)
    assert event.payload["WEB_TERMINAL_WINDOW_ID"] == str(WINDOW_ID)
    assert event.payload["usage"] == {
        "input_tokens": 9370,
        "cache_read_input_tokens": 13824,
        "cache_creation_input_tokens": 7,
        "output_tokens": 19,
        "total_tokens": 23220,
    }
    assert event.payload["attributes"]["session.id"] == "claude-session-1"
    assert event.payload["attributes"]["model"] == "claude-sonnet-4-6"
    assert "content" not in event.payload
    assert "message" not in event.payload


def test_managed_events_from_claude_code_otlp_metrics_ignores_other_clients() -> None:
    payload = _otlp_token_metrics_payload()
    resource = payload["resourceMetrics"][0]["resource"]
    resource["attributes"][0] = _attribute("web_terminal.client_id", str(UUID(int=0)))

    assert managed_events_from_claude_code_otlp_metrics(payload, client_id=CLIENT_ID) == []


@pytest.mark.asyncio
async def test_claude_code_otel_metrics_receiver_accepts_otlp_http_json() -> None:
    sent = []

    async def send_event(message):
        sent.append(message)

    receiver = ClaudeCodeOtelMetricsReceiver(send_event, client_id=CLIENT_ID)
    await receiver.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", receiver.port)
        body = json.dumps(_otlp_token_metrics_payload()).encode("utf-8")
        writer.write(
            b"POST /v1/metrics HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()
        response = await reader.read(1024)
        writer.close()
        await writer.wait_closed()
    finally:
        await receiver.close()

    assert response.startswith(b"HTTP/1.1 200 OK")
    assert len(sent) == 1
    assert sent[0].type == "ai_event"
    assert sent[0].client_id == CLIENT_ID
    assert sent[0].window_id == WINDOW_ID
    assert sent[0].payload["payload"]["usage"]["total_tokens"] == 23220
