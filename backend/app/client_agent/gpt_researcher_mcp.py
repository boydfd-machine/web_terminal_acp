from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

SERVER_NAME = "gpt-researcher"
PROTOCOL_VERSION = "2024-11-05"
DEFAULT_PACKAGE = "gpt-researcher>=0.14,<0.15"
_RESEARCHERS: dict[str, Any] = {}


def main() -> None:
    server = GptResearcherMcp()
    for message in _read_messages():
        try:
            response = server.handle(message)
        except Exception as exc:
            response = _error_response(message.get("id"), -32603, str(exc))
        if response is not None:
            _send(response)


class GptResearcherMcp:
    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        if request_id is None:
            return None
        method = message.get("method")
        if method == "initialize":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            return _result_response(
                request_id,
                {
                    "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                    "capabilities": {"tools": {}, "resources": {}},
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
            with contextlib.redirect_stdout(sys.stderr):
                result = _jsonable(asyncio.run(_call_tool(str(name), args)))
        except Exception as exc:
            return _tool_error(request_id, str(exc))
        return _result_response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
            },
        )


async def _call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "deep_research":
        researcher = _new_researcher(_required_string(args, "query"), args)
        await researcher.conduct_research()
        research_id = str(uuid.uuid4())
        _RESEARCHERS[research_id] = researcher
        return {
            "research_id": research_id,
            "query": _required_string(args, "query"),
            "context": _maybe_call(researcher, "get_research_context"),
            "sources": _maybe_call(researcher, "get_research_sources"),
            "source_urls": _maybe_call(researcher, "get_source_urls"),
        }
    if name == "quick_search":
        researcher = _new_researcher(_required_string(args, "query"), args)
        results = await researcher.quick_search(query=_required_string(args, "query"))
        search_id = str(uuid.uuid4())
        _RESEARCHERS[search_id] = researcher
        return {"search_id": search_id, "query": _required_string(args, "query"), "search_results": results}
    if name == "write_report":
        researcher = _researcher(_required_string(args, "research_id"))
        report = await researcher.write_report(custom_prompt=args.get("custom_prompt"))
        return {
            "report": report,
            "sources": _maybe_call(researcher, "get_research_sources"),
            "costs": _maybe_call(researcher, "get_costs"),
        }
    if name == "get_research_sources":
        researcher = _researcher(_required_string(args, "research_id"))
        return {
            "sources": _maybe_call(researcher, "get_research_sources"),
            "source_urls": _maybe_call(researcher, "get_source_urls"),
        }
    if name == "get_research_context":
        researcher = _researcher(_required_string(args, "research_id"))
        return {"context": _maybe_call(researcher, "get_research_context")}
    raise ValueError(f"unknown tool: {name}")


def _new_researcher(query: str, args: dict[str, Any]) -> Any:
    GPTResearcher = _gpt_researcher_class()
    kwargs: dict[str, Any] = {"query": query}
    for key in ("report_type", "report_source", "tone", "mcp_strategy"):
        value = args.get(key)
        if isinstance(value, str) and value:
            kwargs[key] = value
    return GPTResearcher(**kwargs)


def _gpt_researcher_class() -> Any:
    _ensure_gpt_researcher_package()
    module = importlib.import_module("gpt_researcher")
    return module.GPTResearcher


def _ensure_gpt_researcher_package() -> None:
    target = Path(
        os.environ.get(
            "WEB_TERMINAL_GPT_RESEARCHER_SITE",
            str(Path.home() / ".web-terminal-acp" / "gpt-researcher-mcp" / "site"),
        )
    ).expanduser()
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    try:
        importlib.import_module("gpt_researcher")
        return
    except ImportError:
        pass

    target.mkdir(parents=True, exist_ok=True)
    package = os.environ.get("WEB_TERMINAL_GPT_RESEARCHER_PACKAGE", DEFAULT_PACKAGE)
    env = {
        **os.environ,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--target", str(target), package],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"failed to install {package}: {detail}")
    importlib.invalidate_caches()
    importlib.import_module("gpt_researcher")


def _researcher(research_id: str) -> Any:
    researcher = _RESEARCHERS.get(research_id)
    if researcher is None:
        raise ValueError(f"research not found: {research_id}")
    return researcher


def _maybe_call(target: Any, method: str) -> Any:
    func = getattr(target, method, None)
    if not callable(func):
        return None
    try:
        return func()
    except Exception as exc:
        return {"error": str(exc)}


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        pass
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _required_string(args: dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required argument: {name}")
    return value.strip()


def _tools() -> list[dict[str, Any]]:
    return [
        _tool(
            "deep_research",
            "Conduct GPT Researcher deep web research on a query.",
            {
                "query": _string(),
                "report_type": _string(),
                "report_source": _string(),
                "tone": _string(),
                "mcp_strategy": _string(),
            },
            required=("query",),
        ),
        _tool(
            "quick_search",
            "Run a faster GPT Researcher search optimized for speed over depth.",
            {"query": _string()},
            required=("query",),
        ),
        _tool(
            "write_report",
            "Write a report from a previous deep_research result.",
            {"research_id": _string(), "custom_prompt": _string()},
            required=("research_id",),
        ),
        _tool(
            "get_research_sources",
            "Return sources from a previous deep_research result.",
            {"research_id": _string()},
            required=("research_id",),
        ),
        _tool(
            "get_research_context",
            "Return full context from a previous deep_research result.",
            {"research_id": _string()},
            required=("research_id",),
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


def _string() -> dict[str, str]:
    return {"type": "string"}


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
