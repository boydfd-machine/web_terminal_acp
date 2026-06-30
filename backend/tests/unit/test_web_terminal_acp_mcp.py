import io
import json
from types import SimpleNamespace

from app.client_agent import gpt_researcher_mcp as gpt_mcp
from app.client_agent import web_terminal_acp_mcp as mcp


def _framed(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def test_stdio_mcp_reads_framed_messages(monkeypatch):
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    tools_list = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    stdin = SimpleNamespace(buffer=io.BytesIO(_framed(initialize) + _framed(tools_list)))
    monkeypatch.setattr(mcp.sys, "stdin", stdin)

    messages = list(mcp._read_messages())

    assert messages == [initialize, tools_list]


def test_stdio_mcp_reads_newline_delimited_messages(monkeypatch):
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    tools_list = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    payload = (
        json.dumps(initialize, separators=(",", ":")).encode("utf-8")
        + b"\n"
        + json.dumps(tools_list, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )
    stdin = SimpleNamespace(buffer=io.BytesIO(payload))
    monkeypatch.setattr(mcp.sys, "stdin", stdin)

    messages = list(mcp._read_messages())

    assert messages == [initialize, tools_list]


def test_stdio_mcp_sends_newline_delimited_messages(monkeypatch):
    stdout_buffer = io.BytesIO()
    stdout = SimpleNamespace(buffer=stdout_buffer)
    monkeypatch.setattr(mcp.sys, "stdout", stdout)

    mcp._send({"jsonrpc": "2.0", "id": 1, "result": {}})

    output = stdout_buffer.getvalue()
    assert output.endswith(b"\n")
    assert b"Content-Length" not in output
    assert json.loads(output.decode("utf-8")) == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_mcp_server_lists_tools(monkeypatch):
    monkeypatch.setenv("WEB_TERMINAL_SERVER_URL", "https://control.example.com/")
    monkeypatch.setenv("WEB_TERMINAL_CLIENT_ID", "client-1")
    monkeypatch.setenv("WEB_TERMINAL_WINDOW_ID", "window-1")
    server = mcp.WebTerminalAcpMcp()

    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {
        "list_clients",
        "list_windows",
        "create_window",
        "send_input",
        "capture_output",
        "wait_for_output",
        "upsert_artifact_plugin_preview",
    } <= tool_names


def test_mcp_server_calls_web_terminal_with_source_headers(monkeypatch):
    monkeypatch.setenv("WEB_TERMINAL_SERVER_URL", "https://control.example.com/")
    monkeypatch.setenv("WEB_TERMINAL_CLIENT_ID", "client-1")
    monkeypatch.setenv("WEB_TERMINAL_WINDOW_ID", "window-1")
    monkeypatch.setenv("WEB_TERMINAL_MCP_TOKEN", "token-1")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["data"] = request.data
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(mcp.urllib.request, "urlopen", fake_urlopen)
    server = mcp.WebTerminalAcpMcp()

    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "send_input",
                "arguments": {
                    "target_client_id": "target-1",
                    "window_id": "window-2",
                    "input": "pwd",
                },
            },
        }
    )

    assert response["result"]["structuredContent"] == {"ok": True}
    assert captured["url"] == "https://control.example.com/api/mcp/acp/windows/input"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 610
    assert captured["headers"]["Authorization"] == "Bearer token-1"
    assert captured["headers"]["X-web-terminal-source-client-id"] == "client-1"
    assert captured["headers"]["X-web-terminal-source-window-id"] == "window-1"
    assert json.loads(captured["data"].decode("utf-8")) == {
        "target_client_id": "target-1",
        "window_id": "window-2",
        "input": "pwd",
    }


def test_mcp_server_calls_artifact_plugin_preview_upsert(monkeypatch):
    monkeypatch.setenv("WEB_TERMINAL_SERVER_URL", "https://control.example.com/")
    monkeypatch.setenv("WEB_TERMINAL_CLIENT_ID", "client-1")
    monkeypatch.setenv("WEB_TERMINAL_WINDOW_ID", "window-1")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"id": "preview-1", "status": "valid"}'

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["data"] = request.data
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(mcp.urllib.request, "urlopen", fake_urlopen)
    server = mcp.WebTerminalAcpMcp()

    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "upsert_artifact_plugin_preview",
                "arguments": {
                    "preview_id": "preview-1",
                    "title": "Preview",
                    "python_source": "ARTIFACT_KIND = 'demo'",
                    "prompt_template": "prompt",
                    "html_template": "<html></html>",
                    "json_schema": {"type": "object"},
                    "demo_content_json": {"title": "Preview"},
                },
            },
        }
    )

    assert response["result"]["structuredContent"] == {"id": "preview-1", "status": "valid"}
    assert captured["url"] == "https://control.example.com/api/mcp/acp/artifact-plugin-previews/upsert"
    assert captured["method"] == "POST"
    assert captured["headers"]["X-web-terminal-source-client-id"] == "client-1"
    assert captured["headers"]["X-web-terminal-source-window-id"] == "window-1"
    assert json.loads(captured["data"].decode("utf-8")) == {
        "preview_id": "preview-1",
        "title": "Preview",
        "python_source": "ARTIFACT_KIND = 'demo'",
        "prompt_template": "prompt",
        "html_template": "<html></html>",
        "json_schema": {"type": "object"},
        "demo_content_json": {"title": "Preview"},
    }


def test_gpt_researcher_mcp_lists_research_tools():
    response = gpt_mcp.GptResearcherMcp().handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )

    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {
        "deep_research",
        "quick_search",
        "write_report",
        "get_research_sources",
        "get_research_context",
    } <= tool_names


def test_gpt_researcher_mcp_reads_newline_delimited_messages(monkeypatch):
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    stdin = SimpleNamespace(
        buffer=io.BytesIO(json.dumps(initialize, separators=(",", ":")).encode("utf-8") + b"\n")
    )
    monkeypatch.setattr(gpt_mcp.sys, "stdin", stdin)

    messages = list(gpt_mcp._read_messages())

    assert messages == [initialize]


def test_gpt_researcher_mcp_sends_newline_delimited_messages(monkeypatch):
    stdout_buffer = io.BytesIO()
    stdout = SimpleNamespace(buffer=stdout_buffer)
    monkeypatch.setattr(gpt_mcp.sys, "stdout", stdout)

    gpt_mcp._send({"jsonrpc": "2.0", "id": 1, "result": {}})

    output = stdout_buffer.getvalue()
    assert output.endswith(b"\n")
    assert b"Content-Length" not in output
    assert json.loads(output.decode("utf-8")) == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_gpt_researcher_mcp_runs_research_with_fake_package(monkeypatch):
    gpt_mcp._RESEARCHERS.clear()

    class FakeResearcher:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def conduct_research(self):
            return None

        def get_research_context(self):
            return "research context"

        def get_research_sources(self):
            return [{"title": "Source", "href": "https://example.com"}]

        def get_source_urls(self):
            return ["https://example.com"]

    monkeypatch.setattr(gpt_mcp, "_gpt_researcher_class", lambda: FakeResearcher)

    response = gpt_mcp.GptResearcherMcp().handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "deep_research",
                "arguments": {"query": "AI agents", "report_type": "deep"},
            },
        }
    )

    result = response["result"]["structuredContent"]
    assert result["query"] == "AI agents"
    assert result["context"] == "research context"
    assert result["source_urls"] == ["https://example.com"]
    assert result["research_id"] in gpt_mcp._RESEARCHERS
    assert gpt_mcp._RESEARCHERS[result["research_id"]].kwargs == {
        "query": "AI agents",
        "report_type": "deep",
    }
