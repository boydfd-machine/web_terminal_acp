from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.client_agent.ai_events import ManagedAiEvent
from app.services.runtime.protocol import AgentMessage

logger = logging.getLogger(__name__)

CLAUDE_CODE_OTEL_METRICS_SOURCE = "otel://claude-code/metrics"
MAX_OTLP_REQUEST_BYTES = 2 * 1024 * 1024
_TOKEN_USAGE_METRIC_NAME = "claude_code.token.usage"
_TOKEN_TYPE_FIELDS = {
    "input": "input_tokens",
    "output": "output_tokens",
    "cacheRead": "cache_read_input_tokens",
    "cacheCreation": "cache_creation_input_tokens",
}


@dataclass(frozen=True)
class _TokenUsageGroup:
    window_id: UUID
    attributes: dict[str, str]
    usage: dict[str, int]


class ClaudeCodeOtelMetricsReceiver:
    def __init__(self, send_event, *, client_id: UUID, host: str = "127.0.0.1", port: int = 0) -> None:
        self._send_event = send_event
        self._client_id = client_id
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None

    @property
    def endpoint(self) -> str:
        return f"http://{self._host}:{self.port}/v1/metrics"

    @property
    def port(self) -> int:
        if self._server is None:
            return self._port
        socket = self._server.sockets[0]
        return int(socket.getsockname()[1])

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_connection, self._host, self._port)

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle_request(reader, writer)
        except Exception:
            logger.exception("failed to receive Claude Code OTLP metrics")
            await _write_response(writer, 500, b"")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_line = await reader.readline()
        if not request_line:
            await _write_response(writer, 400, b"")
            return
        try:
            method, path, _version = request_line.decode("ascii", errors="replace").strip().split(" ", 2)
        except ValueError:
            await _write_response(writer, 400, b"")
            return

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            name, separator, value = line.decode("latin1").partition(":")
            if separator:
                headers[name.strip().lower()] = value.strip()

        if method != "POST" or path != "/v1/metrics":
            await _write_response(writer, 404, b"")
            return
        content_length = _positive_int(headers.get("content-length"))
        if content_length is None or content_length > MAX_OTLP_REQUEST_BYTES:
            await _write_response(writer, 413, b"")
            return

        body = await reader.readexactly(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            await _write_response(writer, 400, b"")
            return

        for event in managed_events_from_claude_code_otlp_metrics(payload, client_id=self._client_id):
            await self._send_event(
                AgentMessage(
                    type="ai_event",
                    client_id=event.client_id,
                    window_id=event.window_id,
                    payload={
                        "provider": event.provider,
                        "source_path": event.source_path,
                        "offset": event.offset,
                        "cursor": event.cursor,
                        "project_path": event.project_path,
                        "payload": event.payload,
                    },
                )
            )
        await _write_response(writer, 200, b"{}")


def managed_events_from_claude_code_otlp_metrics(
    payload: dict[str, Any],
    *,
    client_id: UUID,
) -> list[ManagedAiEvent]:
    grouped: dict[tuple[UUID, tuple[tuple[str, str], ...]], _TokenUsageGroup] = {}
    for resource_metric in _list_value(payload.get("resourceMetrics")):
        if not isinstance(resource_metric, dict):
            continue
        resource_attributes = _attributes(resource_metric.get("resource"))
        if resource_attributes.get("web_terminal.client_id") != str(client_id):
            continue
        window_id = _uuid(resource_attributes.get("web_terminal.window_id"))
        if window_id is None:
            continue

        for metric in _iter_metrics(resource_metric):
            if metric.get("name") != _TOKEN_USAGE_METRIC_NAME:
                continue
            for point in _data_points(metric):
                attributes = {**resource_attributes, **_attributes(point)}
                token_type = attributes.get("type")
                field = _TOKEN_TYPE_FIELDS.get(token_type or "")
                value = _number_value(point)
                if field is None or value is None or value <= 0:
                    continue
                group_attributes = {
                    key: value
                    for key, value in attributes.items()
                    if key not in {"type", "web_terminal.client_id", "web_terminal.window_id"}
                }
                key = (window_id, tuple(sorted(group_attributes.items())))
                group = grouped.get(key)
                if group is None:
                    group = _TokenUsageGroup(window_id, group_attributes, defaultdict(int))
                    grouped[key] = group
                group.usage[field] = group.usage.get(field, 0) + value

    events: list[ManagedAiEvent] = []
    for index, group in enumerate(grouped.values()):
        usage = dict(group.usage)
        usage["total_tokens"] = sum(usage.values())
        payload_json = {
            "provider": "claude_code",
            "type": "otel_metric",
            "name": _TOKEN_USAGE_METRIC_NAME,
            "attributes": group.attributes,
            "usage": usage,
            "WEB_TERMINAL_CLIENT_ID": str(client_id),
            "WEB_TERMINAL_WINDOW_ID": str(group.window_id),
        }
        events.append(
            ManagedAiEvent(
                provider="claude_code",
                client_id=client_id,
                window_id=group.window_id,
                source_path=CLAUDE_CODE_OTEL_METRICS_SOURCE,
                offset=None,
                cursor=index,
                project_path=None,
                payload=payload_json,
            )
        )
    return events


def _iter_metrics(resource_metric: dict[str, Any]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for scope_metric in _list_value(resource_metric.get("scopeMetrics")):
        if not isinstance(scope_metric, dict):
            continue
        for metric in _list_value(scope_metric.get("metrics")):
            if isinstance(metric, dict):
                metrics.append(metric)
    return metrics


def _data_points(metric: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for key in ("sum", "gauge", "histogram"):
        value = metric.get(key)
        if isinstance(value, dict):
            points.extend(point for point in _list_value(value.get("dataPoints")) if isinstance(point, dict))
    return points


def _attributes(value: Any) -> dict[str, str]:
    if isinstance(value, dict) and isinstance(value.get("attributes"), list):
        raw_attributes = value.get("attributes")
    elif isinstance(value, list):
        raw_attributes = value
    else:
        return {}
    parsed: dict[str, str] = {}
    for item in raw_attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        attr_value = _attribute_value(item.get("value"))
        if isinstance(key, str) and attr_value is not None:
            parsed[key] = attr_value
    return parsed


def _attribute_value(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        raw_value = value.get(key)
        if raw_value is not None:
            return str(raw_value)
    return None


def _number_value(point: dict[str, Any]) -> int | None:
    for key in ("asInt", "asDouble", "value"):
        parsed = _positive_int(point.get(key))
        if parsed is not None:
            return parsed
    return None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0:
        return int(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed >= 0:
            return int(parsed)
    return None


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


async def _write_response(writer: asyncio.StreamWriter, status: int, body: bytes) -> None:
    reason = {200: "OK", 400: "Bad Request", 404: "Not Found", 413: "Payload Too Large", 500: "Error"}.get(
        status,
        "Error",
    )
    headers = (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    writer.write(headers + body)
    await writer.drain()
