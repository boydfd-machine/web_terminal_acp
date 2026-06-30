import io
import zipfile

from tests.unit.test_agent_config_service_support import *


def _skill_archive(skill_id: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
    return buffer.getvalue()


def test_system_builtins_are_overridable_without_web_terminal_mcp(tmp_path: Path) -> None:
    overridden = agent_config_service.install_system_skill_from_zip(
        "agent-creator",
        _skill_archive("agent-creator"),
        home=tmp_path,
    )
    assert section_items(overridden, "skills")["agent-creator"].origin == "system_config"

    reset = agent_config_service.reset_system_agent_config_item(
        "skills",
        "agent-creator",
        home=tmp_path,
    )
    assert section_items(reset, "skills")["agent-creator"].origin == "system_builtin"

    config = agent_config_service.list_system_agent_config(home=tmp_path)
    mcp = section_items(config, "mcp")
    assert "web-terminal-acp-mcp" not in mcp
    assert "gpt-researcher" not in mcp
    with pytest.raises(ValueError, match="system mcp server not found"):
        agent_config_service.system_mcp_detail("gpt-researcher", home=tmp_path)
    with pytest.raises(ValueError, match="system mcp server not found"):
        agent_config_service.system_mcp_detail("web-terminal-acp-mcp", home=tmp_path)


def test_system_config_does_not_materialize_web_terminal_mcp_for_windows(tmp_path: Path) -> None:
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    managed_config_path = managed / "config.toml"
    managed_config = managed_config_path.read_text(encoding="utf-8") if managed_config_path.is_file() else ""
    assert '[mcp_servers."web-terminal-acp-mcp"]' not in managed_config
    assert not (managed / "mcp.disabled.json").is_file()
