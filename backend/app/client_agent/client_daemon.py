from __future__ import annotations

import re
import shlex
from pathlib import Path

from app.client_agent.logging_setup import STDOUT_LOG_FILENAME


def client_daemon_command(
    *,
    app_path: str | Path,
    python_path: str | Path,
    config_path: str | Path,
    npm_bin_path: str | Path | None = None,
    stdout_log_path: str | Path | None = None,
) -> str:
    environment_prefix = ""
    if npm_bin_path is not None:
        environment_prefix = f'PATH="{npm_bin_path}:$PATH" '
    command = (
        f"cd {_shell_path(app_path)} && "
        f"{environment_prefix}"
        f"PYTHONPATH={_shell_path(app_path)} "
        f"{_shell_path(python_path)} -m app.client_agent "
        f"--config {_shell_path(config_path)}"
    )
    if stdout_log_path is not None:
        command += f" >> {shlex.quote(str(stdout_log_path))} 2>&1"
    return command


def kill_existing_client_processes_command(config_path: str | Path) -> str:
    config = str(config_path)
    if config.startswith("~/"):
        escaped_config = ".*/" + re.escape(config[2:])
    else:
        escaped_config = re.escape(config)
    pattern = "python.*-m app[.]client_agent.*--config " + escaped_config
    quoted_pattern = shlex.quote(pattern)
    return f"""for pid in $(pgrep -f {quoted_pattern} || true); do
  if [ "$pid" != "$$" ]; then kill "$pid" >/dev/null 2>&1 || true; fi
done
sleep 1
for pid in $(pgrep -f {quoted_pattern} || true); do
  if [ "$pid" != "$$" ]; then kill -9 "$pid" >/dev/null 2>&1 || true; fi
done"""


def start_client_daemon_command(
    *,
    install_path: str | Path,
    app_path: str | Path,
    python_path: str | Path,
    config_path: str | Path,
    daemon_name: str,
    npm_bin_path: str | Path | None = None,
) -> str:
    install = str(install_path)
    stdout_log_path = f"{install}/logs/{STDOUT_LOG_FILENAME}"
    command = client_daemon_command(
        app_path=app_path,
        python_path=python_path,
        config_path=config_path,
        npm_bin_path=npm_bin_path,
        stdout_log_path=stdout_log_path,
    )
    return "\n".join(
        [
            "set -e",
            f"mkdir -p {_shell_path(install)}/logs",
            _write_systemd_service_command(
                install_path=install,
                daemon_name=daemon_name,
                command=command,
            ),
            _write_launchd_plist_command(
                install_path=install,
                daemon_name=daemon_name,
                command=command,
            ),
            f"systemctl --user stop {shlex.quote(daemon_name + '.service')} "
            ">/dev/null 2>&1 || true",
            f"launchctl bootout gui/$(id -u) {_launchd_plist_path(daemon_name)} "
            ">/dev/null 2>&1 || true",
            f"tmux kill-session -t {shlex.quote(daemon_name)} >/dev/null 2>&1 || true",
            kill_existing_client_processes_command(config_path),
            "if command -v systemctl >/dev/null 2>&1 "
            "&& systemctl --user status >/dev/null 2>&1; then",
            f"  systemctl --user daemon-reload || true",
            f"  systemctl --user enable --now {shlex.quote(daemon_name + '.service')}",
            "elif command -v launchctl >/dev/null 2>&1 "
            "&& [ \"$(uname -s 2>/dev/null || true)\" = \"Darwin\" ]; then",
            f"  launchctl bootstrap gui/$(id -u) {_launchd_plist_path(daemon_name)}",
            f"  launchctl enable gui/$(id -u)/{shlex.quote(daemon_name)} || true",
            f"  launchctl kickstart -k gui/$(id -u)/{shlex.quote(daemon_name)}",
            "else",
            f"  tmux kill-session -t {shlex.quote(daemon_name)} >/dev/null 2>&1 || true",
            f"  tmux new-session -d -s {shlex.quote(daemon_name)} {shlex.quote(command)}",
            "fi",
        ]
    )


def _write_systemd_service_command(*, install_path: str, daemon_name: str, command: str) -> str:
    service_dir = "$HOME/.config/systemd/user"
    service_path = f"{service_dir}/{daemon_name}.service"
    return (
        f"mkdir -p {service_dir} && "
        f"cat > {service_path} <<'WEB_TERMINAL_ACP_SYSTEMD'\n"
        "[Unit]\n"
        "Description=Web Terminal ACP client agent\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart=/usr/bin/env bash -lc {shlex.quote(command)}\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
        "WEB_TERMINAL_ACP_SYSTEMD"
    )


def _write_launchd_plist_command(*, install_path: str, daemon_name: str, command: str) -> str:
    plist_path = _launchd_plist_path(daemon_name)
    return (
        "mkdir -p \"$HOME/Library/LaunchAgents\" && "
        f"cat > {plist_path} <<'WEB_TERMINAL_ACP_LAUNCHD'\n"
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n"
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{daemon_name}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/bin/bash</string>\n"
        "    <string>-lc</string>\n"
        f"    <string>{_xml_escape(command)}</string>\n"
        "  </array>\n"
        "  <key>RunAtLoad</key>\n"
        "  <true/>\n"
        "  <key>KeepAlive</key>\n"
        "  <true/>\n"
        "</dict>\n"
        "</plist>\n"
        "WEB_TERMINAL_ACP_LAUNCHD"
    )


def _launchd_plist_path(daemon_name: str) -> str:
    return f"\"$HOME/Library/LaunchAgents/{daemon_name}.plist\""


def _shell_path(value: str | Path) -> str:
    text = str(value)
    if text == "~":
        return "~"
    if text.startswith("~/"):
        rest = text[2:]
        return "~/" + shlex.quote(rest) if rest else "~"
    return shlex.quote(text)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
