from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SERVER_NAME = "web-terminal-acp-mcp"
PROTOCOL_VERSION = "2024-11-05"


def main() -> None:
    server = WebTerminalAcpMcp()
    for message in _read_messages():
        try:
            response = server.handle(message)
        except Exception as exc:
            response = _error_response(None, -32603, str(exc))
        if response is not None:
            _send(response)


class WebTerminalAcpMcp:
    def __init__(self) -> None:
        self._server_url = _required_env("WEB_TERMINAL_SERVER_URL").rstrip("/")
        self._source_client_id = _required_env("WEB_TERMINAL_CLIENT_ID")
        self._source_window_id = _required_env("WEB_TERMINAL_WINDOW_ID")
        self._mcp_token = os.environ.get("WEB_TERMINAL_MCP_TOKEN")

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None:
            return None
        if method == "initialize":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            requested_version = params.get("protocolVersion")
            return _result_response(
                request_id,
                {
                    "protocolVersion": requested_version or PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
                },
            )
        if method == "ping":
            return _result_response(request_id, {})
        if method == "tools/list":
            return _result_response(request_id, {"tools": _tools()})
        if method == "tools/call":
            return self._handle_tool_call(request_id, message.get("params"))
        return _error_response(request_id, -32601, f"method not found: {method}")

    def _handle_tool_call(self, request_id: object, params: object) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _error_response(request_id, -32602, "invalid tools/call params")
        name = params.get("name")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        try:
            result = self._call_tool(str(name), args)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return _tool_error(request_id, f"HTTP {exc.code}: {detail}")
        except Exception as exc:
            return _tool_error(request_id, str(exc))
        return _result_response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
            },
        )

    def _call_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_clients":
            return self._request("GET", "/api/mcp/acp/clients")
        if name == "list_windows":
            client_id = _required_arg(args, "client_id")
            return self._request("GET", f"/api/mcp/acp/clients/{_quote(client_id)}/windows")
        if name == "create_window":
            return self._request("POST", "/api/mcp/acp/windows", _payload(args))
        if name == "send_input":
            return self._request("POST", "/api/mcp/acp/windows/input", _payload(args))
        if name == "capture_output":
            return self._request("POST", "/api/mcp/acp/windows/capture", _payload(args))
        if name == "wait_for_output":
            return self._request("POST", "/api/mcp/acp/windows/wait-for-output", _payload(args))
        if name == "read_project_todo":
            return self._request("POST", "/api/mcp/acp/project-todos/read", _payload(args))
        if name == "upsert_artifact_plugin_preview":
            return self._request("POST", "/api/mcp/acp/artifact-plugin-previews/upsert", _payload(args))
        raise ValueError(f"unknown tool: {name}")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self._server_url}{path}",
            data=data,
            method=method,
            headers=self._headers(payload is not None),
        )
        with urllib.request.urlopen(request, timeout=610) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    def _headers(self, has_body: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Web-Terminal-Source-Client-Id": self._source_client_id,
            "X-Web-Terminal-Source-Window-Id": self._source_window_id,
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        if self._mcp_token:
            headers["Authorization"] = f"Bearer {self._mcp_token}"
        return headers


def _tools() -> list[dict[str, Any]]:
    return [
        _tool("list_clients", "List schedulable Web Terminal clients.", {}),
        _tool(
            "list_windows",
            "List active terminal windows on a client.",
            {"client_id": _string()},
            required=("client_id",),
        ),
        _tool(
            "create_window",
            "Create a terminal window on a target client.",
            {
                "target_client_id": _string(),
                "cwd": _string(),
                "shell_command": _string(),
                "agent_client": _string(),
                "prompt": _string(),
                "folder_path": _string(),
            },
            required=("target_client_id",),
        ),
        _tool(
            "send_input",
            "Send terminal input to a window.",
            {
                "target_client_id": _string(),
                "window_id": _string(),
                "input": _string(),
                "append_enter": {"type": "boolean"},
            },
            required=("target_client_id", "window_id", "input"),
        ),
        _tool(
            "capture_output",
            "Capture terminal output from a window.",
            {
                "target_client_id": _string(),
                "window_id": _string(),
                "history_lines": _integer(1, 10000),
                "max_bytes": _integer(1, 1048576),
            },
            required=("target_client_id", "window_id"),
        ),
        _tool(
            "wait_for_output",
            "Wait until terminal output contains target text.",
            {
                "target_client_id": _string(),
                "window_id": _string(),
                "contains": _string(),
                "timeout_seconds": _number(0.1, 600),
                "poll_interval_seconds": _number(0.1, 30),
                "history_lines": _integer(1, 10000),
            },
            required=("target_client_id", "window_id", "contains"),
        ),
        _tool(
            "read_project_todo",
            "Read project todo/card context by todo ID.",
            {
                "todo_id": _string(),
                "include_agent_record": {"type": "boolean"},
                "include_worktree": {"type": "boolean"},
                "include_related": {"type": "boolean"},
                "agent_record_message_limit": _integer(1, 500),
            },
            required=("todo_id",),
        ),
        _tool(
            "upsert_artifact_plugin_preview",
            "Create or update a live artifact plugin preview bound to this Web Terminal window.",
            {
                "preview_id": _string(),
                "title": _string(),
                "python_source": _string(),
                "prompt_template": _string(),
                "html_template": _string(),
                "json_schema": {"type": "object"},
                "demo_content_json": {"type": "object"},
            },
            required=(
                "title",
                "python_source",
                "prompt_template",
                "html_template",
                "json_schema",
            ),
        ),
    ]


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": list(required),
            "additionalProperties": False,
        },
    }


def _payload(args: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in args.items() if value is not None}


def _string() -> dict[str, str]:
    return {"type": "string"}


def _integer(minimum: int, maximum: int) -> dict[str, int | str]:
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _number(minimum: float, maximum: float) -> dict[str, float | str]:
    return {"type": "number", "minimum": minimum, "maximum": maximum}


def _required_arg(args: dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required argument: {name}")
    return value


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def _result_response(request_id: object, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _tool_error(request_id: object, message: str) -> dict[str, Any]:
    return _result_response(
        request_id,
        {"content": [{"type": "text", "text": message}], "isError": True},
    )


def _error_response(request_id: object, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _read_messages():
    stream = sys.stdin.buffer
    while True:
        first_line = stream.readline()
        if not first_line:
            return
        if first_line in {b"\n", b"\r\n"}:
            continue
        if _looks_like_json_message(first_line):
            yield json.loads(first_line.decode("utf-8"))
            continue
        headers = [first_line]
        while True:
            line = stream.readline()
            if not line:
                return
            if line in {b"\n", b"\r\n"}:
                break
            headers.append(line)
        length = _content_length(headers)
        if length is None:
            continue
        body = stream.read(length)
        if not body:
            return
        yield json.loads(body.decode("utf-8"))


def _content_length(headers: list[bytes]) -> int | None:
    for header in headers:
        name, separator, value = header.partition(b":")
        if separator and name.strip().lower() == b"content-length":
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _looks_like_json_message(line: bytes) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(b"{") or stripped.startswith(b"[")


def _send(message: dict[str, Any]) -> None:
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
