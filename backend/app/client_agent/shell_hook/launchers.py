import base64
import gzip
import posixpath
import re
import shlex
import sys
import textwrap
from dataclasses import dataclass
from uuid import UUID

from app.agent_plugins import get_agent_plugin_registry
from app.client_agent.agent_commands import (
    agent_command_name_from_command,
    agent_command_with_permission_flag,
)

_SAFE_SHELL_VALUE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")
_SHELL_FUNCTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHELL_CASE_WORD = re.compile(r"^[A-Za-z0-9_.-]+$")
AGENT_NPM_GLOBAL_BIN = "~/.web-terminal-acp/npm-global/bin"


@dataclass(frozen=True)
class ManagedShellCommand:
    command: str
    command_capture_supported: bool
    hook_script: str | None = None


def build_managed_shell_command(
    *,
    shell: str,
    client_id: UUID | str,
    window_id: UUID | str,
    server_url: str,
    project_path: str | None = None,
    agent_ops_token: str | None = None,
    agent_otel_metrics_endpoint: str | None = None,
) -> ManagedShellCommand:
    env = {
        "WEB_TERMINAL_CLIENT_ID": str(client_id),
        "WEB_TERMINAL_WINDOW_ID": str(window_id),
        "WEB_TERMINAL_SERVER_URL": server_url,
        "WEB_TERMINAL_COMMAND_HOOK": "1",
        "WEB_TERMINAL_PROJECT_PATH": project_path or "",
        **_agent_shell_environment(str(window_id)),
    }
    if agent_ops_token:
        env["WEB_TERMINAL_AGENT_OPS_TOKEN"] = agent_ops_token
    if agent_otel_metrics_endpoint:
        env["WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT"] = agent_otel_metrics_endpoint
    assignments = " ".join(
        [
            'PATH="$HOME/.web-terminal-acp/npm-global/bin:$PATH"',
            *(f"{key}={_shell_quote(value)}" for key, value in env.items()),
        ]
    )
    shell_name = posixpath.basename(shell)

    if shell_name == "bash":
        from app.client_agent.shell_hook.bash_hooks import _bash_hook_script

        hook_script = _bash_hook_script()
        return ManagedShellCommand(
            command=f"{assignments} {_shell_quote(shell)} -lc {_shell_quote(_bash_launcher(shell, hook_script))}",
            command_capture_supported=True,
            hook_script=hook_script,
        )
    if shell_name == "zsh":
        from app.client_agent.shell_hook.zsh_hooks import _zsh_hook_script

        hook_script = _zsh_hook_script()
        return ManagedShellCommand(
            command=f"{assignments} {_shell_quote(shell)} -fc {_shell_quote(_zsh_launcher(shell, hook_script))}",
            command_capture_supported=True,
            hook_script=hook_script,
        )

    return ManagedShellCommand(
        command=f"{assignments} /bin/sh -c {_shell_quote(_direct_launcher(shell))}",
        command_capture_supported=False,
    )


def _agent_shell_environment(window_id: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for plugin in get_agent_plugin_registry().all():
        for key, value in plugin.storage.shell_env_aliases.items():
            env[key] = value.format(window_id=window_id)
    for plugin in get_agent_plugin_registry().all():
        for key, value in plugin.storage.env.items():
            if key == "CODEX_HOME":
                continue
            env[key] = value.format(window_id=window_id)
    return env


def _shell_words(values: tuple[str, ...]) -> str:
    return " ".join(_shell_quote(value) for value in values)


def _shell_quote(value: str) -> str:
    if value and _SAFE_SHELL_VALUE.fullmatch(value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def _agent_home_prepare_for_command_script() -> str:
    lines = ["__wt_prepare_agent_home() {", 'case "$1" in']
    for plugin in get_agent_plugin_registry().all():
        function_name = plugin.storage.shell_prepare_function
        if function_name is None:
            continue
        if not _SHELL_FUNCTION_NAME.fullmatch(function_name):
            raise ValueError(f"invalid agent shell prepare function: {function_name}")
        case_words = plugin.command.command_names
        if any(not _SHELL_CASE_WORD.fullmatch(command_name) for command_name in case_words):
            raise ValueError(f"invalid agent shell command name for case pattern: {case_words!r}")
        lines.append(f"{'|'.join(case_words)}) {function_name};;")
    lines.extend(["esac", "}"])
    return "\n".join(lines)


def _bash_launcher(shell: str, hook_script: str) -> str:
    quoted_shell = _shell_quote(shell)
    return f"""__web_terminal_rc=$(mktemp)
chmod 600 "$__web_terminal_rc"
{_decode_hook_to_path("$__web_terminal_rc", hook_script, "WT_B")}
exec {quoted_shell} --rcfile "$__web_terminal_rc" -i
"""


def _zsh_launcher(shell: str, hook_script: str) -> str:
    quoted_shell = _shell_quote(shell)
    return f"""__web_terminal_zdotdir=$(mktemp -d)
chmod 700 "$__web_terminal_zdotdir"
{_decode_hook_to_path("$__web_terminal_zdotdir/.zshrc", hook_script, "WT_Z")}
export ZDOTDIR="$__web_terminal_zdotdir"
exec {quoted_shell} -i
"""


def _decode_hook_to_path(path: str, hook_script: str, marker: str) -> str:
    payload = "\n".join(
        textwrap.wrap(base64.b64encode(gzip.compress(hook_script.encode("utf-8"))).decode("ascii"), 1000)
    )
    return f"""{_shell_quote(sys.executable)} -c 'import base64,gzip,sys; sys.stdout.write(gzip.decompress(base64.b64decode(sys.stdin.read())).decode("utf-8"))' > "{path}" <<'{marker}'
{payload}
{marker}
__web_terminal_decode_status=$?
[ "$__web_terminal_decode_status" -eq 0 ] || exit "$__web_terminal_decode_status"
"""


def _direct_launcher(shell: str) -> str:
    command = _exec_command(shell)
    if _is_direct_agent_command(shell):
        command_name = _direct_agent_command_name(shell)
        prepare_direct_agent = (
            f"__web_terminal_prepare_direct_agent_launch {_shell_quote(command_name)}"
            if command_name is not None
            else "__web_terminal_prepare_agent_command_path"
        )
        return f"""{_agent_environment_script()}
if __web_terminal_missing_claude_env; then
  __web_terminal_load_zshrc_env
fi
{prepare_direct_agent}
__web_terminal_agent_exit=0
{command} || __web_terminal_agent_exit=$?
printf '\\n[web-terminal] agent command exited with status %s; opening shell...\\n' "$__web_terminal_agent_exit"
{_direct_agent_fallback_shell_launcher()}
"""
    return f"""{_agent_environment_script()}
if __web_terminal_missing_claude_env; then
  __web_terminal_load_zshrc_env
fi
exec {command}
"""


def _direct_agent_fallback_shell_launcher() -> str:
    from app.client_agent.shell_hook.bash_hooks import _bash_hook_script
    from app.client_agent.shell_hook.zsh_hooks import _zsh_hook_script

    return f"""__web_terminal_fallback_shell="${{SHELL:-/bin/sh}}"
case "${{__web_terminal_fallback_shell##*/}}" in
  bash)
    __web_terminal_rc=$(mktemp)
    chmod 600 "$__web_terminal_rc"
{_decode_hook_to_path("$__web_terminal_rc", _bash_hook_script(), "WT_DB")}
    exec "$__web_terminal_fallback_shell" --rcfile "$__web_terminal_rc" -i
    ;;
  zsh)
    __web_terminal_zdotdir=$(mktemp -d)
    chmod 700 "$__web_terminal_zdotdir"
{_decode_hook_to_path("$__web_terminal_zdotdir/.zshrc", _zsh_hook_script(), "WT_DZ")}
    export ZDOTDIR="$__web_terminal_zdotdir"
    exec "$__web_terminal_fallback_shell" -i
    ;;
  *)
    exec "$__web_terminal_fallback_shell" -i
    ;;
esac"""


def _agent_environment_script() -> str:
    from app.client_agent.shell_hook.bash_hooks import _agent_environment_script as build_script

    return build_script()


def _exec_command(value: str) -> str:
    command = agent_command_with_permission_flag(value)
    if command is None:
        return _shell_quote(value)
    command_name = _direct_agent_command_name(command)
    if command_name == "claude":
        return _direct_claude_code_command(command)
    return _direct_agent_command_with_env(command, command_name)


def _direct_claude_code_command(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return command
    if not tokens or posixpath.basename(tokens[0]) != "claude":
        return command
    return " ".join(
        [_shell_quote("__web_terminal_run_claude_code_command"), *(_shell_quote(token) for token in tokens[1:])]
    )


def _direct_agent_command_with_env(command: str, command_name: str | None) -> str:
    if command_name not in {"agy", "agy-p"}:
        return command
    return (
        "HOME=\"$WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME\" "
        "AGY_PROXY_WORKSPACE_LINK_ROOT=\"$AGY_PROXY_WORKSPACE_LINK_ROOT\" "
        f"{command}"
    )


def _is_direct_agent_command(value: str) -> bool:
    return _direct_agent_command_name(value) is not None


def _direct_agent_command_name(value: str) -> str | None:
    command_name = agent_command_name_from_command(value)
    return posixpath.basename(command_name) if command_name is not None else None


def _agent_permission_wrapper_script() -> str:
    lines = ["__web_terminal_install_agent_permission_wrappers() {"]
    for plugin in get_agent_plugin_registry().all():
        for command_name in plugin.command.command_names:
            lines.append(f"  unalias {command_name} 2>/dev/null || true")
            permission_flag = plugin.command.permission_flag
            if not _SHELL_FUNCTION_NAME.fullmatch(command_name):
                helper = (
                    f"__web_terminal_run_agent_command_with_permission {command_name} {_shell_quote(permission_flag)}"
                    if permission_flag
                    else f"__web_terminal_run_agent_command {command_name}"
                )
                lines.append(f"  alias {command_name}={_shell_quote(helper)}")
                continue
            lines.append(f"  {command_name}() {{")
            if permission_flag:
                quoted_flag = _shell_quote(permission_flag)
                lines.append(
                    f"    __web_terminal_run_agent_command_with_permission {command_name} {quoted_flag} \"$@\""
                )
            else:
                lines.append(f"    __web_terminal_run_agent_command {command_name} \"$@\"")
            lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


_CODEX_TRUST_MARKER_PY = r'''import json, os, re, sys, tempfile
path = os.environ.get("WEB_TERMINAL_CODEX_CONFIG_PATH")
cwd_env = os.environ.get("WEB_TERMINAL_TRUST_CWD") or os.getcwd()
project_env = os.environ.get("WEB_TERMINAL_PROJECT_PATH") or ""
if not path:
    sys.exit(0)

projects = []
for raw_path in (cwd_env, project_env):
    if not raw_path:
        continue
    try:
        real_path = os.path.realpath(raw_path)
    except Exception:
        real_path = raw_path
    if real_path and real_path not in projects:
        projects.append(real_path)
if not projects:
    sys.exit(0)

try:
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
except FileNotFoundError:
    original = ""
except Exception:
    sys.exit(0)

TABLE_HEADER_RE = re.compile(r"^\s*\[[^\n]+\]\s*(?:#.*)?$")
TRUST_LEVEL_RE = re.compile(r"\s*trust_level\s*=")


def toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def project_header(project):
    return "[projects." + toml_string(project) + "]"


def is_table_header(line):
    return bool(TABLE_HEADER_RE.match(line.strip()))


def header_matches(line, header):
    stripped = line.strip()
    return stripped == header or stripped.startswith(header + " #")


def upsert_project(lines, project):
    header = project_header(project)
    output = []
    found = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if header_matches(line, header):
            found = True
            output.append(header)
            index += 1
            saw_trust = False
            while index < len(lines) and not is_table_header(lines[index]):
                if TRUST_LEVEL_RE.match(lines[index]):
                    if not saw_trust:
                        output.append('trust_level = "trusted"')
                        saw_trust = True
                    index += 1
                    continue
                output.append(lines[index])
                index += 1
            if not saw_trust:
                output.append('trust_level = "trusted"')
            continue
        output.append(line)
        index += 1
    if found:
        return output
    if output and output[-1].strip():
        output.append("")
    output.extend([header, 'trust_level = "trusted"'])
    return output


lines = original.splitlines()
for project in projects:
    lines = upsert_project(lines, project)
updated = "\n".join(lines).rstrip() + "\n"
if updated == original:
    sys.exit(0)

parent = os.path.dirname(path) or "."
try:
    os.makedirs(parent, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".config.toml.", dir=parent)
except Exception:
    sys.exit(0)
try:
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        f.write(updated)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
except Exception:
    try:
        os.unlink(tmp)
    except Exception:
        pass
'''


def _codex_trust_marker_script() -> str:
    return (
        "__web_terminal_mark_codex_folder_trusted() {\n"
        "  [ -n \"${WEB_TERMINAL_CODEX_HOME:-}\" ] || return 0\n"
        "  [ -n \"${PWD:-}\" ] || return 0\n"
        "  command -v python3 >/dev/null 2>&1 || return 0\n"
        "  mkdir -p \"$WEB_TERMINAL_CODEX_HOME\" 2>/dev/null || return 0\n"
        "  __web_terminal_codex_config_path=\"$WEB_TERMINAL_CODEX_HOME/config.toml\"\n"
        "  if [ -L \"$__web_terminal_codex_config_path\" ]; then\n"
        "    __web_terminal_codex_config_real=\"$(readlink -f \"$__web_terminal_codex_config_path\" 2>/dev/null || true)\"\n"
        "    rm -f \"$__web_terminal_codex_config_path\" 2>/dev/null || return 0\n"
        "    if [ -n \"$__web_terminal_codex_config_real\" ] && [ -e \"$__web_terminal_codex_config_real\" ]; then\n"
        "      cp -p \"$__web_terminal_codex_config_real\" \"$__web_terminal_codex_config_path\" 2>/dev/null || return 0\n"
        "      chmod 600 \"$__web_terminal_codex_config_path\" 2>/dev/null || true\n"
        "    fi\n"
        "  fi\n"
        "  WEB_TERMINAL_CODEX_CONFIG_PATH=\"$__web_terminal_codex_config_path\" WEB_TERMINAL_TRUST_CWD=\"$PWD\" WEB_TERMINAL_PROJECT_PATH=\"${WEB_TERMINAL_PROJECT_PATH:-}\" python3 - <<'WEB_TERMINAL_CODEX_TRUST_PY' || return 0\n"
        + _CODEX_TRUST_MARKER_PY
        + "WEB_TERMINAL_CODEX_TRUST_PY\n"
        "}\n"
    )


_CLAUDE_TRUST_MARKER_PY = r'''import json, os, sys, tempfile
path = os.environ.get("WEB_TERMINAL_CLAUDE_JSON_PATH")
cwd_env = os.environ.get("WEB_TERMINAL_TRUST_CWD") or os.getcwd()
if not path:
    sys.exit(0)
try:
    cwd = os.path.realpath(cwd_env)
except Exception:
    cwd = cwd_env
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
projects = data.get("projects")
if not isinstance(projects, dict):
    projects = {}
    data["projects"] = projects
entry = projects.get(cwd)
if not isinstance(entry, dict):
    entry = {}
    projects[cwd] = entry
if entry.get("hasTrustDialogAccepted") is True:
    sys.exit(0)
entry["hasTrustDialogAccepted"] = True
seen = entry.get("projectOnboardingSeenCount")
if not isinstance(seen, int) or seen < 1:
    entry["projectOnboardingSeenCount"] = 1
parent = os.path.dirname(path) or "."
try:
    handle, tmp = tempfile.mkstemp(prefix=".claude.json.", dir=parent)
except Exception:
    sys.exit(0)
try:
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
except Exception:
    try:
        os.unlink(tmp)
    except Exception:
        pass
'''


def _claude_trust_marker_script() -> str:
    return (
        "__web_terminal_mark_claude_code_folder_trusted() {\n"
        "  [ -n \"${WEB_TERMINAL_CLAUDE_CODE_HOME:-}\" ] || return 0\n"
        "  [ -n \"${PWD:-}\" ] || return 0\n"
        "  command -v python3 >/dev/null 2>&1 || return 0\n"
        "  __web_terminal_claude_json_path=\"$WEB_TERMINAL_CLAUDE_CODE_HOME/.claude.json\"\n"
        "  [ -e \"$__web_terminal_claude_json_path\" ] || return 0\n"
        "  if [ -L \"$__web_terminal_claude_json_path\" ]; then\n"
        "    __web_terminal_claude_json_real=\"$(readlink -f \"$__web_terminal_claude_json_path\" 2>/dev/null || true)\"\n"
        "    [ -n \"$__web_terminal_claude_json_real\" ] || return 0\n"
        "    [ -e \"$__web_terminal_claude_json_real\" ] || return 0\n"
        "    rm -f \"$__web_terminal_claude_json_path\" 2>/dev/null || return 0\n"
        "    cp -p \"$__web_terminal_claude_json_real\" \"$__web_terminal_claude_json_path\" 2>/dev/null || return 0\n"
        "    chmod 600 \"$__web_terminal_claude_json_path\" 2>/dev/null || true\n"
        "  fi\n"
        "  WEB_TERMINAL_CLAUDE_JSON_PATH=\"$__web_terminal_claude_json_path\" WEB_TERMINAL_TRUST_CWD=\"$PWD\" python3 - <<'WEB_TERMINAL_CLAUDE_TRUST_PY' || return 0\n"
        + _CLAUDE_TRUST_MARKER_PY
        +         "WEB_TERMINAL_CLAUDE_TRUST_PY\n"
        "}\n"
    )


_CURSOR_TRUST_MARKER_PY = r'''import json, os, sys, tempfile
from datetime import datetime, timezone

cursor_data = os.environ.get("WEB_TERMINAL_CURSOR_DATA_DIR") or os.environ.get("CURSOR_DATA_DIR")
cwd_env = os.environ.get("WEB_TERMINAL_TRUST_CWD") or os.getcwd()
project_env = os.environ.get("WEB_TERMINAL_PROJECT_PATH") or ""
if not cursor_data:
    sys.exit(0)

paths = []
for raw_path in (cwd_env, project_env):
    if not raw_path:
        continue
    try:
        real_path = os.path.realpath(raw_path)
    except Exception:
        real_path = raw_path
    if real_path and real_path not in paths:
        paths.append(real_path)
if not paths:
    sys.exit(0)


def encode_path(path):
    return path.lstrip("/").replace("/", "-")


def trust_payload(path):
    return {
        "trustedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspacePath": path,
    }


for path in paths:
    project_dir = os.path.join(cursor_data, "projects", encode_path(path))
    trust_path = os.path.join(project_dir, ".workspace-trusted")
    payload = trust_payload(path)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        if os.path.isfile(trust_path):
            with open(trust_path, "r", encoding="utf-8") as handle:
                existing = handle.read()
            if existing == serialized:
                continue
    except Exception:
        pass
    try:
        os.makedirs(project_dir, exist_ok=True)
        handle, tmp = tempfile.mkstemp(prefix=".workspace-trusted.", dir=project_dir)
    except Exception:
        continue
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(serialized)
        os.replace(tmp, trust_path)
        try:
            os.chmod(trust_path, 0o600)
        except Exception:
            pass
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
'''


def _cursor_trust_marker_script() -> str:
    return (
        "__web_terminal_mark_cursor_folder_trusted() {\n"
        "  [ -n \"${WEB_TERMINAL_CURSOR_HOME:-}\" ] || return 0\n"
        "  [ -n \"${PWD:-}\" ] || return 0\n"
        "  command -v python3 >/dev/null 2>&1 || return 0\n"
        "  local managed_cursor\n"
        "  case \"$WEB_TERMINAL_CURSOR_HOME\" in\n"
        '    "~/"*) managed_cursor="$HOME/${WEB_TERMINAL_CURSOR_HOME#"~/"}" ;;\n'
        "    *) managed_cursor=\"$WEB_TERMINAL_CURSOR_HOME\" ;;\n"
        "  esac\n"
        "  mkdir -p \"$managed_cursor/projects\" 2>/dev/null || return 0\n"
        "  WEB_TERMINAL_CURSOR_DATA_DIR=\"$managed_cursor\" WEB_TERMINAL_TRUST_CWD=\"$PWD\" WEB_TERMINAL_PROJECT_PATH=\"${WEB_TERMINAL_PROJECT_PATH:-}\" python3 - <<'WEB_TERMINAL_CURSOR_TRUST_PY' || return 0\n"
        + _CURSOR_TRUST_MARKER_PY
        + "WEB_TERMINAL_CURSOR_TRUST_PY\n"
        "}\n"
    )
