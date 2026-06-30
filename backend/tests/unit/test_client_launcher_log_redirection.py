"""Regression tests for client agent launcher stdout/stderr redirection.

The Python logger attaches a RotatingFileHandler to ``client.log`` directly, so
shell redirection must NOT also point to ``client.log`` (otherwise rotation
breaks the shell-held file descriptor and log lines split between ``client.log``
and ``client.log.<N>``). Launcher scripts must redirect stdout/stderr to a
separate ``client.stdout.log`` file so import errors / unhandled tracebacks are
still captured.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.client_agent.logging_setup import STDOUT_LOG_FILENAME
from app.client_agent.updater import _updater_script
from app.contexts.clients.application.client_update import _legacy_update_python


def test_updater_script_redirects_stdout_to_dedicated_file():
    script = _updater_script(
        _StubConfig(),
        job_id="job-1",
        install_path=Path("/tmp/web-terminal-install"),
        staging_root=Path("/tmp/web-terminal-install/updates/job-1"),
    )
    # Critical: stderr/stdout must NOT land in client.log (would break rotation).
    assert ">> /tmp/web-terminal-install/logs/client.log" not in script
    assert f">> /tmp/web-terminal-install/logs/{STDOUT_LOG_FILENAME}" in script
    assert "Restart=always" in script
    assert "<key>KeepAlive</key>" in script
    assert "2>&1" in script


def test_legacy_update_python_redirects_stdout_to_dedicated_file():
    script = _legacy_update_python("legacy-1")
    # The Python source uses "client.stdout.log" as the literal; no "client.log"
    # string should remain as a standalone literal.
    assert '"client.stdout.log"' in script
    assert '"client.log"' not in script


def test_register_client_direct_script_redirects_stdout_to_dedicated_file():
    backend_app = Path(__file__).resolve().parents[2]
    script_path = backend_app / "app" / "resources" / "register-client-direct.sh"
    script = script_path.read_text(encoding="utf-8")
    assert 'logs_path / "client.log"' not in script
    assert f'logs_path / "{STDOUT_LOG_FILENAME}"' in script
    assert 'subprocess.check_call(["systemctl", "--user", "enable", "--now",' in script
    assert "<key>KeepAlive</key>" in script


@dataclass(frozen=True)
class _StubConfig:
    server_url: str = "https://example.test"
    client_id: str = "00000000-0000-0000-0000-000000000001"
    token: str = "test-token"
    client_daemon_session: str = "web_terminal_acp_client"
