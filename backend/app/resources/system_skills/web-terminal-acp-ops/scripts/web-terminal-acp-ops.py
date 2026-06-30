#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OPS_PREFIX = "/api/agent-ops"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _run(args, _HttpClient(args))
    except Exception as exc:
        print(f"web-terminal-acp-ops: {exc}", file=sys.stderr)
        return 1
    if args.raw and isinstance(result, str):
        print(result, end="" if result.endswith("\n") else "\n")
        return 0
    indent = None if args.compact else 2
    print(json.dumps(result, ensure_ascii=False, indent=indent))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call Web Terminal ACP HTTP operations.")
    parser.add_argument("--server-url", default=os.environ.get("WEB_TERMINAL_SERVER_URL"))
    parser.add_argument("--source-client-id", default=os.environ.get("WEB_TERMINAL_CLIENT_ID"))
    parser.add_argument("--source-window-id", default=os.environ.get("WEB_TERMINAL_WINDOW_ID"))
    parser.add_argument("--ops-token", default=os.environ.get("WEB_TERMINAL_AGENT_OPS_TOKEN"))
    parser.add_argument("--auth-token", default=os.environ.get("WEB_TERMINAL_AUTH_TOKEN"))
    parser.add_argument("--timeout", type=float, default=610.0)
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")
    parser.add_argument("--raw", action="store_true", help="Print raw HTML/text for HTML commands.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("list-clients")
    windows = subcommands.add_parser("list-windows")
    windows.add_argument("client_id")
    create = subcommands.add_parser("create-window")
    create.add_argument("target_client_id")
    create.add_argument("--cwd")
    create.add_argument("--shell-command")
    create.add_argument("--agent-client")
    create.add_argument("--prompt")
    create.add_argument("--folder-path")
    send = subcommands.add_parser("send-input")
    send.add_argument("target_client_id")
    send.add_argument("window_id")
    send.add_argument("input")
    send.add_argument("--append-enter", action="store_true")
    capture = subcommands.add_parser("capture-output")
    capture.add_argument("target_client_id")
    capture.add_argument("window_id")
    capture.add_argument("--history-lines", type=int)
    capture.add_argument("--max-bytes", type=int)
    wait = subcommands.add_parser("wait-for-output")
    wait.add_argument("target_client_id")
    wait.add_argument("window_id")
    wait.add_argument("contains")
    wait.add_argument("--timeout-seconds", type=float)
    wait.add_argument("--poll-interval-seconds", type=float)
    wait.add_argument("--history-lines", type=int)
    todo = subcommands.add_parser("read-project-todo")
    todo.add_argument("todo_id")
    todo.add_argument("--no-agent-record", dest="include_agent_record", action="store_false", default=None)
    todo.add_argument("--no-worktree", dest="include_worktree", action="store_false", default=None)
    todo.add_argument("--no-related", dest="include_related", action="store_false", default=None)
    todo.add_argument("--agent-record-message-limit", type=int)
    todo_search = subcommands.add_parser("search-project-todos")
    for option in ("query", "--project-path"):
        todo_search.add_argument(option)
    todo_search.add_argument("--limit", type=int, default=25)
    todo_search.add_argument("--offset", type=int, default=0)
    _project_todo_create_parser(subcommands.add_parser("create-project-todo"))
    _project_todo_patch_parser(subcommands.add_parser("patch-project-todo"))
    _project_todo_dispatch_parser(subcommands.add_parser("dispatch-project-todo"))
    preview = subcommands.add_parser("read-agent-preview")
    preview.add_argument("client_id")
    preview.add_argument("window_id")
    preview.add_argument("--limit", type=int, default=200)
    preview.add_argument("--offset", type=int, default=0)
    preview.add_argument("--detail", action="store_true")
    artifacts = subcommands.add_parser("list-artifacts")
    artifacts.add_argument("client_id")
    artifacts.add_argument("window_id")
    artifacts.add_argument("--limit", type=int, default=50)
    artifacts.add_argument("--offset", type=int, default=0)
    artifacts.add_argument("--artifact-scope", choices=("terminal", "project"), default="terminal")
    artifacts.add_argument("--project-path")
    for name in ("read-artifact", "read-artifact-html"):
        item = subcommands.add_parser(name)
        item.add_argument("client_id")
        item.add_argument("window_id")
        item.add_argument("artifact_id")
        item.add_argument("--artifact-scope", choices=("terminal", "project"), default="terminal")
        item.add_argument("--project-path")
    for name in ("read-card-artifact", "read-card-artifact-html"):
        item = subcommands.add_parser(name)
        item.add_argument("todo_id")
        item.add_argument("artifact_ref")
    upsert = subcommands.add_parser("upsert-artifact-plugin-preview")
    upsert.add_argument("--preview-id")
    upsert.add_argument("--title", required=True)
    _text_input(upsert, "python-source")
    _text_input(upsert, "prompt-template")
    _text_input(upsert, "html-template")
    _json_input(upsert, "json-schema")
    _json_input(upsert, "demo-content-json", required=False)
    previews = subcommands.add_parser("list-artifact-plugin-previews")
    previews.add_argument("client_id")
    previews.add_argument("window_id")
    previews.add_argument("--limit", type=int, default=50)
    previews.add_argument("--offset", type=int, default=0)
    subcommands.add_parser("read-artifact-plugin-preview").add_argument("preview_id")
    subcommands.add_parser("read-artifact-plugin-preview-html").add_argument("preview_id")
    return parser


def _project_todo_create_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--target-client-id")
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--status", choices=("TODO", "BLOCKED"))
    parser.add_argument("--todo-type-id")
    parser.add_argument("--parent-todo-id")
    _json_input(parser, "body-json", required=False)


def _project_todo_patch_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("todo_id")
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--target-client-id")
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--clear-description", action="store_true")
    parser.add_argument("--status", choices=("TODO", "BLOCKED", "DISPATCHED", "AWAITING_REVIEW", "DONE"))
    parser.add_argument("--todo-type-id")
    parser.add_argument("--parent-todo-id")
    _json_input(parser, "body-json", required=False)


def _project_todo_dispatch_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("todo_id")
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--target-client-id")
    parser.add_argument("--agent")
    parser.add_argument("--command", dest="agent_command")
    parser.add_argument("--profile-id")
    parser.add_argument("--dispatch-mode", choices=("submit", "compose"))
    parser.add_argument("--prompt")
    parser.add_argument("--output-language")
    parser.add_argument("--dispatch-after-todo-id", action="append", dest="dispatch_after_todo_ids")
    _json_input(parser, "body-json", required=False)


def _run(args: argparse.Namespace, client: "_HttpClient") -> object:
    command = args.command
    if command == "list-clients":
        return client.ops("GET", "/clients")
    if command == "list-windows":
        return client.ops("GET", f"/clients/{_quote(args.client_id)}/windows")
    if command == "create-window":
        return client.ops("POST", "/windows", _payload(args, "target_client_id", "cwd", "shell_command", "agent_client", "prompt", "folder_path"))
    if command == "send-input":
        return client.ops("POST", "/windows/input", _payload(args, "target_client_id", "window_id", "input", "append_enter"))
    if command == "capture-output":
        return client.ops("POST", "/windows/capture", _payload(args, "target_client_id", "window_id", "history_lines", "max_bytes"))
    if command == "wait-for-output":
        return client.ops("POST", "/windows/wait-for-output", _payload(args, "target_client_id", "window_id", "contains", "timeout_seconds", "poll_interval_seconds", "history_lines"))
    if command == "read-project-todo":
        return client.ops("POST", "/project-todos/read", _payload(args, "todo_id", "include_agent_record", "include_worktree", "include_related", "agent_record_message_limit"))
    if command == "search-project-todos":
        return _search_project_todos(client, args)
    if command == "create-project-todo":
        return _create_project_todo(client, args)
    if command == "patch-project-todo":
        return _patch_project_todo(client, args)
    if command == "dispatch-project-todo":
        return _dispatch_project_todo(client, args)
    if command == "read-agent-preview":
        return _read_agent_preview(client, args)
    if command == "list-artifacts":
        return _list_artifacts(client, args)
    if command == "read-artifact":
        return _read_artifact(client, args.client_id, args.window_id, args.artifact_id, args.artifact_scope, args.project_path)
    if command == "read-artifact-html":
        return _read_artifact_html(client, args.client_id, args.window_id, args.artifact_id, args.artifact_scope, args.project_path)
    if command in {"read-card-artifact", "read-card-artifact-html"}:
        return _read_card_artifact(client, args.todo_id, args.artifact_ref, html=command.endswith("-html"))
    if command == "upsert-artifact-plugin-preview":
        return client.ops("POST", "/artifact-plugin-previews/upsert", _preview_payload(args))
    if command == "list-artifact-plugin-previews":
        params = urllib.parse.urlencode({"limit": args.limit, "offset": args.offset})
        return client.ops("GET", f"/clients/{_quote(args.client_id)}/windows/{_quote(args.window_id)}/artifact-plugin-previews?{params}")
    if command == "read-artifact-plugin-preview":
        return client.ops("GET", f"/artifact-plugin-previews/{_quote(args.preview_id)}")
    if command == "read-artifact-plugin-preview-html":
        return client.ops("GET", f"/artifact-plugin-previews/{_quote(args.preview_id)}/html", expect="text")
    raise RuntimeError(f"unknown command: {command}")


class _HttpClient:
    def __init__(self, args: argparse.Namespace) -> None:
        if not args.server_url:
            raise RuntimeError("WEB_TERMINAL_SERVER_URL is not set")
        self.server_url = args.server_url.rstrip("/")
        self.source_client_id = args.source_client_id
        self.source_window_id = args.source_window_id
        self.ops_token = args.ops_token
        self.auth_token = args.auth_token
        self.timeout = args.timeout

    def ops(self, method: str, path: str, body: dict[str, object] | None = None, *, expect: str = "json") -> object:
        if not self.source_client_id or not self.source_window_id:
            raise RuntimeError("WEB_TERMINAL_CLIENT_ID and WEB_TERMINAL_WINDOW_ID are required")
        return self.request(method, f"{OPS_PREFIX}{path}", body, ops=True, expect=expect)

    def request(self, method: str, path: str, body: dict[str, object] | None = None, *, ops: bool = False, expect: str = "json") -> object:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(f"{self.server_url}{path}", data=data, method=method, headers=self._headers(data is not None, ops))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        if expect == "text":
            return raw
        return json.loads(raw) if raw else {}

    def _headers(self, has_body: bool, ops: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if has_body:
            headers["Content-Type"] = "application/json"
        token = self.ops_token if ops else (self.auth_token or self.ops_token)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if ops:
            headers["X-Web-Terminal-Source-Client-Id"] = self.source_client_id or ""
            headers["X-Web-Terminal-Source-Window-Id"] = self.source_window_id or ""
        return headers


def _read_agent_preview(client: _HttpClient, args: argparse.Namespace) -> object:
    params = {"limit": args.limit, "offset": args.offset, "detail": str(args.detail).lower()}
    return client.ops("GET", f"/clients/{_quote(args.client_id)}/windows/{_quote(args.window_id)}/agent-preview?{_query(params)}")


def _search_project_todos(client: _HttpClient, args: argparse.Namespace) -> object:
    params = {"q": args.query, "project_path": args.project_path, "limit": args.limit, "offset": args.offset}
    return client.ops("GET", f"/project-todos/search?{_query(params)}")


def _create_project_todo(client: _HttpClient, args: argparse.Namespace) -> object:
    payload = _body_json_payload(args)
    payload.update(_payload(args, "title", "description", "status", "todo_type_id", "parent_todo_id"))
    return client.ops("POST", _project_todo_path("", args.project_path, args.target_client_id), payload)


def _patch_project_todo(client: _HttpClient, args: argparse.Namespace) -> object:
    if args.description is not None and args.clear_description:
        raise RuntimeError("use either --description or --clear-description")
    payload = _body_json_payload(args)
    payload.update(_payload(args, "title", "description", "status", "todo_type_id", "parent_todo_id"))
    if args.clear_description:
        payload["description"] = None
    return client.ops("PATCH", _project_todo_path(f"/{_quote(args.todo_id)}", args.project_path, args.target_client_id), payload)


def _dispatch_project_todo(client: _HttpClient, args: argparse.Namespace) -> object:
    payload = _body_json_payload(args)
    agent_launch = dict(payload.get("agent_launch") or {})
    agent_launch.update(_payload(args, "agent", "profile_id"))
    if args.agent_command is not None:
        agent_launch["command"] = args.agent_command
    if agent_launch:
        payload["agent_launch"] = agent_launch
    elif "agent_launch" not in payload:
        raise RuntimeError("--agent is required unless --body-json includes agent_launch")
    payload.update(_payload(args, "dispatch_mode", "prompt", "output_language", "dispatch_after_todo_ids"))
    return client.ops("POST", _project_todo_path(f"/{_quote(args.todo_id)}/dispatch", args.project_path, args.target_client_id), payload)


def _list_artifacts(client: _HttpClient, args: argparse.Namespace) -> object:
    params = {"limit": args.limit, "offset": args.offset, "artifact_scope": args.artifact_scope}
    if args.project_path:
        params["project_path"] = args.project_path
    return client.ops("GET", f"/clients/{_quote(args.client_id)}/windows/{_quote(args.window_id)}/artifacts?{_query(params)}")


def _read_artifact(client: _HttpClient, client_id: str, window_id: str, artifact_id: str, scope: str, project_path: str | None) -> object:
    return client.ops("GET", _artifact_path(client_id, window_id, artifact_id, scope, project_path))


def _read_artifact_html(client: _HttpClient, client_id: str, window_id: str, artifact_id: str, scope: str, project_path: str | None) -> object:
    return client.ops("GET", _artifact_path(client_id, window_id, artifact_id, scope, project_path, html=True), expect="text")


def _read_card_artifact(client: _HttpClient, todo_id: str, artifact_ref: str, *, html: bool) -> object:
    suffix = "/html" if html else ""
    return client.ops("GET", f"/project-todos/{_quote(todo_id)}/artifacts/{_quote(artifact_ref)}{suffix}", expect="text" if html else "json")


def _artifact_path(client_id: str, window_id: str, artifact_id: str, scope: str, project_path: str | None, *, html: bool = False) -> str:
    suffix = "/html" if html else ""
    if scope == "project":
        if not project_path:
            raise RuntimeError("project_path is required for project artifacts")
        return f"/clients/{_quote(client_id)}/windows/{_quote(window_id)}/artifacts/{_quote(artifact_id)}{suffix}?{_query({'artifact_scope': 'project', 'project_path': project_path})}"
    return f"/clients/{_quote(client_id)}/windows/{_quote(window_id)}/artifacts/{_quote(artifact_id)}{suffix}"


def _project_todo_path(suffix: str, project_path: str, target_client_id: str | None = None) -> str:
    return f"/project-todos{suffix}?{_query({'project_path': project_path, 'target_client_id': target_client_id})}"


def _preview_payload(args: argparse.Namespace) -> dict[str, object]:
    payload = {"preview_id": args.preview_id, "title": args.title, "python_source": _arg_text(args, "python_source"), "prompt_template": _arg_text(args, "prompt_template"), "html_template": _arg_text(args, "html_template"), "json_schema": _arg_json(args, "json_schema"), "demo_content_json": _arg_json(args, "demo_content_json", required=False)}
    return {key: value for key, value in payload.items() if value is not None}


def _body_json_payload(args: argparse.Namespace) -> dict[str, object]:
    value = _arg_json(args, "body_json", required=False)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeError("--body-json must be a JSON object")
    return dict(value)


def _payload(args: argparse.Namespace, *keys: str) -> dict[str, object]:
    return {key: getattr(args, key) for key in keys if getattr(args, key) is not None}


def _text_input(parser: argparse.ArgumentParser, name: str) -> None:
    dest = name.replace("-", "_")
    parser.add_argument(f"--{name}", dest=dest)
    parser.add_argument(f"--{name}-file", dest=f"{dest}_file")


def _json_input(parser: argparse.ArgumentParser, name: str, *, required: bool = True) -> None:
    dest = name.replace("-", "_")
    parser.add_argument(f"--{name}", dest=dest)
    parser.add_argument(f"--{name}-file", dest=f"{dest}_file")


def _arg_text(args: argparse.Namespace, name: str) -> str:
    value, path = getattr(args, name), getattr(args, f"{name}_file")
    if value is not None and path is not None:
        raise RuntimeError(f"use either --{name.replace('_', '-')} or --{name.replace('_', '-')}-file")
    if path is not None:
        return Path(path).read_text(encoding="utf-8")
    if value is None:
        raise RuntimeError(f"--{name.replace('_', '-')} is required")
    return value


def _arg_json(args: argparse.Namespace, name: str, *, required: bool = True) -> object:
    value, path = getattr(args, name), getattr(args, f"{name}_file")
    if value is not None and path is not None:
        raise RuntimeError(f"use either --{name.replace('_', '-')} or --{name.replace('_', '-')}-file")
    if path is not None:
        value = Path(path).read_text(encoding="utf-8")
    if value is None:
        if required:
            raise RuntimeError(f"--{name.replace('_', '-')} is required")
        return None
    return json.loads(value)


def _quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def _query(params: dict[str, object]) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})


if __name__ == "__main__":
    raise SystemExit(main())
