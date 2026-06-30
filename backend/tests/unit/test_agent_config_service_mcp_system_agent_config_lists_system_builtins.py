import io
import zipfile

from tests.unit.test_agent_config_service_support import *


def _skill_archive(skill_id: str, name: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{skill_id}/SKILL.md", f"---\nname: {name or skill_id}\n---\n")
        archive.writestr(f"{skill_id}/scripts/run.sh", "echo ok\n")
    return buffer.getvalue()

def test_system_agent_config_lists_system_builtins_and_managed_items(tmp_path: Path) -> None:
    write_skill(tmp_path / ".codex" / "skills" / ".system", "openai-docs")
    write_skill(tmp_path / ".claude" / "skills" / "skills" / ".system", "skill-installer")
    agent_config_service.install_system_skill_from_zip(
        "review-helper",
        _skill_archive("review-helper", "Review Helper"),
        home=tmp_path,
    )
    agent_config_service.upsert_system_mcp_server(
        "system-echo",
        {"type": "stdio", "command": "echo"},
        home=tmp_path,
    )

    config = agent_config_service.list_system_agent_config(home=tmp_path)
    skills = section_items(config, "skills")
    mcp = section_items(config, "mcp")

    assert skills["agent-creator"].origin == "system_builtin"
    assert skills["agent-trace-graph"].origin == "system_builtin"
    assert skills["artifact-plugin-creator"].origin == "system_builtin"
    assert skills["skill-creator"].origin == "system_builtin"
    assert skills["review-helper"].origin == "system_config"
    assert "gpt-researcher" not in mcp
    assert "web-terminal-acp-mcp" not in mcp
    assert mcp["system-echo"].origin == "system_config"

def test_system_mcp_materializes_before_builtin_mcp_for_codex_and_json_agents(tmp_path: Path) -> None:
    agent_config_service.upsert_system_mcp_server(
        "system-echo",
        {
            "type": "stdio",
            "command": "echo",
            "args": ["ok"],
            "env": {"TOKEN": "secret"},
        },
        home=tmp_path,
    )

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="codex-window",
        home=tmp_path,
    )
    agent_config_service.install_builtin_mcp_for_agent_window(
        "codex",
        window_id="codex-window",
        source_client_id="client-1",
        source_window_id="codex-window",
        server_url="https://control.example.com",
        home=tmp_path,
    )
    codex_config = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "codex-window" / "config.toml"
    ).read_text(encoding="utf-8")
    assert '[mcp_servers."system-echo"]' in codex_config
    assert 'args = ["ok"]' in codex_config
    assert 'TOKEN = "secret"' in codex_config
    assert '[mcp_servers."web-terminal-acp-mcp"]' in codex_config

    agent_config_service.install_system_config_for_agent_window(
        "cursor",
        window_id="cursor-window",
        home=tmp_path,
    )
    agent_config_service.install_builtin_mcp_for_agent_window(
        "cursor",
        window_id="cursor-window",
        source_client_id="client-1",
        source_window_id="cursor-window",
        server_url="https://control.example.com",
        home=tmp_path,
    )
    cursor_mcp = json.loads(
        (tmp_path / ".web-terminal-acp" / "cursor-homes" / "cursor-window" / "mcp.json").read_text(
            encoding="utf-8"
        )
    )
    assert cursor_mcp["mcpServers"]["system-echo"]["command"] == "echo"
    assert "web-terminal-acp-mcp" in cursor_mcp["mcpServers"]
