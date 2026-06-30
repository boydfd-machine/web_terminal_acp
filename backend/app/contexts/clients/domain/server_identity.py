from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import socket


_SERVER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


def server_id_from_environment(value: str | None, *, hostname: str | None = None) -> str:
    configured = value.strip() if value is not None else ""
    if configured:
        return configured
    detected_hostname = (hostname or socket.gethostname()).strip()
    return detected_hostname or "server"


def server_key_from_id(server_id: str) -> str:
    normalized = _SERVER_KEY_PATTERN.sub("-", server_id.lower()).strip("-")
    if normalized:
        if len(normalized) <= 48:
            return normalized
        digest = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:8]
        prefix = normalized[:39].strip("-") or "server"
        return f"{prefix}-{digest}"
    digest = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:12]
    return f"server-{digest}"


@dataclass(frozen=True)
class RemoteClientInstance:
    server_id: str
    server_key: str
    base_install_path: str

    @classmethod
    def from_server_id(
        cls,
        server_id: str,
        *,
        base_install_path: str,
    ) -> "RemoteClientInstance":
        return cls(
            server_id=server_id,
            server_key=server_key_from_id(server_id),
            base_install_path=base_install_path.rstrip("/"),
        )

    @property
    def install_path(self) -> str:
        return f"{self.base_install_path}/servers/{self.server_key}"

    @property
    def config_path(self) -> str:
        return f"{self.install_path}/config.json"

    @property
    def app_path(self) -> str:
        return f"{self.install_path}/app"

    @property
    def venv_path(self) -> str:
        return f"{self.install_path}/venv"

    @property
    def requirements_path(self) -> str:
        return f"{self.install_path}/requirements.txt"

    @property
    def session_suffix(self) -> str:
        return self.server_key.replace("-", "_")

    @property
    def tmux_pool_session(self) -> str:
        return f"web_terminal_acp_pool_{self.session_suffix}"

    @property
    def client_daemon_session(self) -> str:
        return f"web_terminal_acp_client_{self.session_suffix}"
