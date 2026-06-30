import json
from pathlib import Path
from uuid import UUID

from app.client_agent.__main__ import client_agent_lock
from app.client_agent.config import ClientAgentConfig
from tests.unit.test_client_agent_config_support import _write_config


def test_load_derives_server_scoped_session_defaults_from_server_key(tmp_path: Path) -> None:
    config_path = tmp_path / "client-agent.json"
    _write_config(config_path, server_url="https://control.example.com/")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    data["server_id"] = "Primary Server"
    data["server_key"] = "primary-server"
    config_path.write_text(json.dumps(data), encoding="utf-8")

    config = ClientAgentConfig.load(config_path)

    assert config.server_id == "Primary Server"
    assert config.server_key == "primary-server"
    assert config.tmux_pool_session == "web_terminal_acp_pool_primary_server"
    assert config.client_daemon_session == "web_terminal_acp_client_primary_server"


def test_client_agent_lock_is_scoped_by_server_key(tmp_path: Path) -> None:
    first = ClientAgentConfig(
        client_id=UUID("12345678-1234-5678-1234-567812345678"),
        token="secret-token",
        server_url="http://control-a.example.com",
        name="edge-client",
        install_path=tmp_path,
        server_id="Server A",
        server_key="server-a",
    )
    second = ClientAgentConfig(
        client_id=UUID("87654321-4321-8765-4321-876543218765"),
        token="secret-token",
        server_url="http://control-b.example.com",
        name="edge-client",
        install_path=tmp_path,
        server_id="Server B",
        server_key="server-b",
    )

    with client_agent_lock(first):
        with client_agent_lock(second):
            assert (tmp_path / "client-agent-server-a.lock").exists()
            assert (tmp_path / "client-agent-server-b.lock").exists()
