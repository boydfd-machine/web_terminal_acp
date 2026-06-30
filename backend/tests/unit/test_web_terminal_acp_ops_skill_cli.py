import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.contexts.agent_profiles.infrastructure.builtin_system_skills import (
    builtin_system_skill_file_content,
)


def test_web_terminal_acp_ops_cli_calls_agent_ops_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = tmp_path / "web-terminal-acp-ops.py"
    cli_content = builtin_system_skill_file_content(
        "web-terminal-acp-ops",
        "scripts/web-terminal-acp-ops.py",
    )
    assert cli_content is not None
    cli.write_text(cli_content, encoding="utf-8")
    module = _load_cli_module(cli)
    requests: list[dict[str, object]] = []
    source_client_id = "11111111-1111-1111-1111-111111111111"
    source_window_id = "22222222-2222-2222-2222-222222222222"
    monkeypatch.setattr(module.urllib.request, "urlopen", _fake_urlopen(requests))

    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "capture-output",
            "target-1",
            "window-1",
            "--history-lines",
            "5",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"text": "captured", "truncated": False}
    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "read-agent-preview",
            "target-1",
            "window-1",
            "--limit",
            "25",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"window_id": "window-1", "messages": []}
    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "search-project-todos",
            "llama",
            "--project-path",
            "/workspace/project",
            "--limit",
            "10",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"query": "llama", "results": []}
    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "create-project-todo",
            "--project-path",
            "/workspace/project",
            "--title",
            "Implement CLI writes",
            "--description",
            "Create from ops",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "todo-1", "title": "Implement CLI writes"}
    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "patch-project-todo",
            "todo-1",
            "--project-path",
            "/workspace/project",
            "--status",
            "BLOCKED",
            "--clear-description",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "todo-1", "status": "BLOCKED"}
    assert module.main(
        [
            "--server-url",
            "https://control.example.com",
            "--source-client-id",
            source_client_id,
            "--source-window-id",
            source_window_id,
            "--ops-token",
            "ops-token",
            "--compact",
            "dispatch-project-todo",
            "todo-1",
            "--project-path",
            "/workspace/project",
            "--agent",
            "codex",
            "--command",
            "codex",
            "--dispatch-mode",
            "compose",
            "--prompt",
            "Run from ops",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "todo-1", "status": "TODO", "dispatch_stage": "STARTING"}
    assert requests[0] == {
        "method": "POST",
        "path": "/api/agent-ops/windows/capture",
        "query": "",
        "authorization": "Bearer ops-token",
        "source_client_id": source_client_id,
        "source_window_id": source_window_id,
        "body": {"target_client_id": "target-1", "window_id": "window-1", "history_lines": 5},
    }
    assert requests[1]["method"] == "GET"
    assert requests[1]["path"] == "/api/agent-ops/clients/target-1/windows/window-1/agent-preview"
    assert requests[1]["query"] == "limit=25&offset=0&detail=false"
    assert requests[2]["method"] == "GET"
    assert requests[2]["path"] == "/api/agent-ops/project-todos/search"
    assert requests[2]["query"] == "q=llama&project_path=%2Fworkspace%2Fproject&limit=10&offset=0"
    assert requests[3] == {
        "method": "POST",
        "path": "/api/agent-ops/project-todos",
        "query": "project_path=%2Fworkspace%2Fproject",
        "authorization": "Bearer ops-token",
        "source_client_id": source_client_id,
        "source_window_id": source_window_id,
        "body": {"title": "Implement CLI writes", "description": "Create from ops"},
    }
    assert requests[4] == {
        "method": "PATCH",
        "path": "/api/agent-ops/project-todos/todo-1",
        "query": "project_path=%2Fworkspace%2Fproject",
        "authorization": "Bearer ops-token",
        "source_client_id": source_client_id,
        "source_window_id": source_window_id,
        "body": {"description": None, "status": "BLOCKED"},
    }
    assert requests[5] == {
        "method": "POST",
        "path": "/api/agent-ops/project-todos/todo-1/dispatch",
        "query": "project_path=%2Fworkspace%2Fproject",
        "authorization": "Bearer ops-token",
        "source_client_id": source_client_id,
        "source_window_id": source_window_id,
        "body": {
            "agent_launch": {"agent": "codex", "command": "codex"},
            "dispatch_mode": "compose",
            "prompt": "Run from ops",
        },
    }


def test_web_terminal_acp_ops_cli_targets_project_todo_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = tmp_path / "web-terminal-acp-ops.py"
    cli_content = builtin_system_skill_file_content(
        "web-terminal-acp-ops",
        "scripts/web-terminal-acp-ops.py",
    )
    assert cli_content is not None
    cli.write_text(cli_content, encoding="utf-8")
    module = _load_cli_module(cli)
    requests: list[dict[str, object]] = []
    source_client_id = "11111111-1111-1111-1111-111111111111"
    source_window_id = "22222222-2222-2222-2222-222222222222"
    target_client_id = "33333333-3333-3333-3333-333333333333"
    monkeypatch.setattr(module.urllib.request, "urlopen", _fake_urlopen(requests))

    common_args = [
        "--server-url",
        "https://control.example.com",
        "--source-client-id",
        source_client_id,
        "--source-window-id",
        source_window_id,
        "--ops-token",
        "ops-token",
        "--compact",
    ]
    assert module.main(
        [
            *common_args,
            "create-project-todo",
            "--project-path",
            "/workspace/project",
            "--target-client-id",
            target_client_id,
            "--title",
            "Create on target",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "todo-1", "title": "Implement CLI writes"}
    assert module.main(
        [
            *common_args,
            "dispatch-project-todo",
            "todo-1",
            "--project-path",
            "/workspace/project",
            "--target-client-id",
            target_client_id,
            "--agent",
            "codex",
            "--command",
            "codex --model gpt-5.5",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"id": "todo-1", "status": "TODO", "dispatch_stage": "STARTING"}

    assert requests[0]["query"] == (
        "project_path=%2Fworkspace%2Fproject&"
        "target_client_id=33333333-3333-3333-3333-333333333333"
    )
    assert requests[1]["query"] == (
        "project_path=%2Fworkspace%2Fproject&"
        "target_client_id=33333333-3333-3333-3333-333333333333"
    )


def _load_cli_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("web_terminal_acp_ops_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_urlopen(requests: list[dict[str, object]]):
    def urlopen(request, timeout: float):
        url = request.full_url
        path = url.removeprefix("https://control.example.com")
        route, _, query = path.partition("?")
        body = request.data.decode("utf-8") if request.data else ""
        requests.append(
            {
                "method": request.get_method(),
                "path": route,
                "query": query,
                "authorization": request.headers.get("Authorization"),
                "source_client_id": request.headers.get("X-web-terminal-source-client-id"),
                "source_window_id": request.headers.get("X-web-terminal-source-window-id"),
                "body": json.loads(body) if body else None,
            }
        )
        if route.endswith("/project-todos/search"):
            payload = {"query": "llama", "results": []}
        elif route.endswith("/project-todos") and request.get_method() == "POST":
            payload = {"id": "todo-1", "title": "Implement CLI writes"}
        elif route.endswith("/project-todos/todo-1") and request.get_method() == "PATCH":
            payload = {"id": "todo-1", "status": "BLOCKED"}
        elif route.endswith("/project-todos/todo-1/dispatch"):
            payload = {"id": "todo-1", "status": "TODO", "dispatch_stage": "STARTING"}
        elif request.get_method() == "GET":
            payload = {"window_id": "window-1", "messages": []}
        else:
            payload = {"text": "captured", "truncated": False}
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    return urlopen


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body
