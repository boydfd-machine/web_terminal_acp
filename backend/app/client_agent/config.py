import os
import pwd
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import model_validator

from app.contexts.clients.domain.server_identity import server_key_from_id
from app.client_agent.stale_window_cleanup import DEFAULT_STALE_WINDOW_CLEANUP_SECONDS


def default_user_shell() -> str:
    shell = os.environ.get("SHELL")
    if shell:
        return shell
    try:
        return pwd.getpwuid(os.getuid()).pw_shell or "/bin/bash"
    except KeyError:
        return "/bin/bash"


class ClientAgentConfig(BaseModel):
    client_id: UUID
    token: str
    server_url: str
    name: str
    install_path: Path
    server_id: str | None = None
    server_key: str | None = None
    tmux_pool_session: str = "web_terminal_acp_pool"
    client_daemon_session: str = "web_terminal_acp_client"
    reconnect_initial_delay_seconds: float = 1
    reconnect_max_delay_seconds: float = 30
    websocket_ping_interval_seconds: float | None = 10
    websocket_ping_timeout_seconds: float | None = 60
    default_shell: str = Field(default_factory=default_user_shell)
    tmux_window_inactive_cleanup_seconds: float = DEFAULT_STALE_WINDOW_CLEANUP_SECONDS

    @classmethod
    def load(cls, path: Path) -> "ClientAgentConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @model_validator(mode="after")
    def derive_server_scoped_defaults(self) -> "ClientAgentConfig":
        if self.server_id is not None and not self.server_key:
            self.server_key = server_key_from_id(self.server_id)
        if self.server_key:
            suffix = self.server_key.replace("-", "_")
            if self.tmux_pool_session == "web_terminal_acp_pool":
                self.tmux_pool_session = f"web_terminal_acp_pool_{suffix}"
            if self.client_daemon_session == "web_terminal_acp_client":
                self.client_daemon_session = f"web_terminal_acp_client_{suffix}"
        return self

    @property
    def lock_filename(self) -> str:
        if self.server_key:
            return f"client-agent-{self.server_key}.lock"
        return "client-agent.lock"

    def _websocket_base_url(self) -> str:
        base_url = self.server_url.rstrip("/")
        if base_url.startswith("https://"):
            return f"wss://{base_url.removeprefix('https://')}"
        if base_url.startswith("http://"):
            return f"ws://{base_url.removeprefix('http://')}"
        return base_url

    @property
    def websocket_url(self) -> str:
        base_url = self._websocket_base_url()
        if base_url.endswith("/api/client-agent/ws"):
            return base_url
        if base_url.endswith("/api/client-agent/bulk-ws"):
            return f"{base_url.removesuffix('/api/client-agent/bulk-ws')}/api/client-agent/ws"
        return f"{base_url}/api/client-agent/ws"

    @property
    def bulk_websocket_url(self) -> str:
        base_url = self._websocket_base_url()
        if base_url.endswith("/api/client-agent/bulk-ws"):
            return base_url
        if base_url.endswith("/api/client-agent/ws"):
            return f"{base_url.removesuffix('/api/client-agent/ws')}/api/client-agent/bulk-ws"
        return f"{base_url}/api/client-agent/bulk-ws"
