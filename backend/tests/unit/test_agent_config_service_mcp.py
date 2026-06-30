import io
import zipfile

from tests.unit.test_agent_config_service_support import *


def _skill_archive(skill_id: str, name: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{skill_id}/SKILL.md", f"---\nname: {name or skill_id}\n---\n")
        archive.writestr(f"{skill_id}/scripts/run.sh", "echo ok\n")
    return buffer.getvalue()

def test_codex_mcp_config_lists_and_toggles_toml_servers(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        "\n".join(
            [
                "[mcp_servers.filesystem]",
                'command = "npx"',
                'args = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]',
                "",
                "[mcp_servers.filesystem.env]",
                'TOKEN = "secret"',
                "",
                '[mcp_servers."remote-http"]',
                'url = "https://example.com/mcp"',
                "",
                "[profiles.default]",
                'model = "gpt-5"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = list_agent_config("codex", home=tmp_path)

    assert section_items(config, "mcp")["filesystem"].enabled is True
    assert section_items(config, "mcp")["remote-http"].enabled is True

    set_agent_config_item_enabled("codex", "mcp", "filesystem", False, home=tmp_path)
    updated = (codex_home / "config.toml").read_text(encoding="utf-8")
    disabled = json.loads((codex_home / "mcp.disabled.json").read_text(encoding="utf-8"))
    assert "[mcp_servers.filesystem]" not in updated
    assert '[mcp_servers."remote-http"]' in updated
    assert "[profiles.default]" in updated
    assert "filesystem" in disabled["mcpServers"]
    disabled_mcp = section_items(list_agent_config("codex", home=tmp_path), "mcp")
    assert disabled_mcp["filesystem"].enabled is False

    set_agent_config_item_enabled("codex", "mcp", "filesystem", True, home=tmp_path)
    restored = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.filesystem]" in restored
    assert "[mcp_servers.filesystem.env]" in restored

def test_apply_agent_config_selection_materializes_codex_mcp_for_window(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\nargs = ["ok"]\n',
        encoding="utf-8",
    )

    apply_agent_config_selection(
        AgentConfigSelection(
            agent="codex",
            sections=[
                AgentConfigSectionSelection(
                    id="mcp",
                    items=[AgentConfigItemSelection(id="filesystem", enabled=False)],
                )
            ],
        ),
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert "[mcp_servers.filesystem]" not in (managed / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.filesystem]" in (codex_home / "config.toml").read_text(encoding="utf-8")

def test_claude_mcp_config_lists_and_toggles_user_and_project_servers(tmp_path: Path) -> None:
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()
    state_path = claude_home / ".claude.json"
    project_key = "/workspace/project"
    state_path.write_text(
        json.dumps(
            {
                "mcpServers": {"user-server": {"type": "stdio", "command": "echo"}},
                "projects": {
                    project_key: {
                        "mcpServers": {
                            "project-server": {"type": "stdio", "command": "pwd"}
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    project_id = agent_config_service._claude_project_mcp_id(project_key, "project-server")

    config = list_agent_config("claude", home=tmp_path)

    assert section_items(config, "mcp")["user:user-server"].enabled is True
    assert section_items(config, "mcp")[project_id].enabled is True

    set_agent_config_item_enabled("claude", "mcp", project_id, False, home=tmp_path)
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert "project-server" not in updated["projects"][project_key]["mcpServers"]
    assert (
        updated[agent_config_service.CLAUDE_DISABLED_MCP_KEY][project_id]["name"]
        == "project-server"
    )
    disabled_mcp = section_items(list_agent_config("claude", home=tmp_path), "mcp")
    assert disabled_mcp[project_id].enabled is False

    set_agent_config_item_enabled("claude", "mcp", project_id, True, home=tmp_path)
    restored = json.loads(state_path.read_text(encoding="utf-8"))
    assert restored["projects"][project_key]["mcpServers"]["project-server"]["command"] == "pwd"

def test_apply_agent_config_selection_materializes_claude_mcp_from_global_state(
    tmp_path: Path,
) -> None:
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"user-server": {"type": "stdio", "command": "echo"}}}),
        encoding="utf-8",
    )

    apply_agent_config_selection(
        AgentConfigSelection(
            agent="claude",
            sections=[
                AgentConfigSectionSelection(
                    id="mcp",
                    items=[AgentConfigItemSelection(id="user:user-server", enabled=False)],
                )
            ],
        ),
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    global_state = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert "user-server" not in managed_state["mcpServers"]
    assert "user-server" in global_state["mcpServers"]

def test_json_mcp_config_lists_and_toggles_cursor_servers(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"filesystem": {"command": "echo", "args": ["ok"]}}}),
        encoding="utf-8",
    )

    mcp_servers = section_items(list_agent_config("cursor", home=tmp_path), "mcp")
    assert mcp_servers["filesystem"].enabled is True

    set_agent_config_item_enabled("cursor", "mcp", "filesystem", False, home=tmp_path)
    active = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    disabled = json.loads((cursor_home / "mcp.disabled.json").read_text(encoding="utf-8"))
    assert "filesystem" not in active["mcpServers"]
    assert disabled["mcpServers"]["filesystem"]["command"] == "echo"

    set_agent_config_item_enabled("cursor", "mcp", "filesystem", True, home=tmp_path)
    restored = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    assert restored["mcpServers"]["filesystem"]["args"] == ["ok"]

def test_agent_profile_mcp_override_materializes_for_window(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\n',
        encoding="utf-8",
    )
    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )

    agent_profile_service.set_agent_profile_config_item_enabled(
        profile.id,
        "codex",
        "mcp",
        "filesystem",
        False,
        home=tmp_path,
    )
    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert "[mcp_servers.filesystem]" not in (managed / "config.toml").read_text(encoding="utf-8")

def test_install_builtin_mcp_materializes_codex_window_server(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\n',
        encoding="utf-8",
    )

    agent_config_service.install_builtin_mcp_for_agent_window(
        "codex",
        window_id="window-1",
        source_client_id="client-1",
        source_window_id="window-1",
        server_url="https://control.example.com",
        mcp_token="mcp-token",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    managed_config = (managed / "config.toml").read_text(encoding="utf-8")
    global_config = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '[mcp_servers."web-terminal-acp-mcp"]' in managed_config
    assert 'args = ["-m", "app.client_agent.web_terminal_acp_mcp"]' in managed_config
    assert "startup_timeout_sec = 120" in managed_config
    assert 'WEB_TERMINAL_CLIENT_ID = "client-1"' in managed_config
    assert 'WEB_TERMINAL_WINDOW_ID = "window-1"' in managed_config
    assert 'WEB_TERMINAL_SERVER_URL = "https://control.example.com"' in managed_config
    assert 'WEB_TERMINAL_MCP_TOKEN = "mcp-token"' in managed_config
    assert "[mcp_servers.filesystem]" in managed_config
    assert "web-terminal-acp-mcp" not in global_config

def test_install_builtin_mcp_materializes_claude_window_server(tmp_path: Path) -> None:
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"user-server": {"type": "stdio", "command": "echo"}}}),
        encoding="utf-8",
    )

    agent_config_service.install_builtin_mcp_for_agent_window(
        "claude",
        window_id="window-1",
        source_client_id="client-1",
        source_window_id="window-1",
        server_url="https://control.example.com",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    global_state = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    builtin = managed_state["mcpServers"]["web-terminal-acp-mcp"]
    assert builtin["command"]
    assert builtin["args"] == ["-m", "app.client_agent.web_terminal_acp_mcp"]
    assert builtin["env"]["WEB_TERMINAL_CLIENT_ID"] == "client-1"
    assert builtin["env"]["WEB_TERMINAL_WINDOW_ID"] == "window-1"
    assert builtin["env"]["WEB_TERMINAL_SERVER_URL"] == "https://control.example.com"
    assert "WEB_TERMINAL_MCP_TOKEN" not in builtin["env"]
    assert "web-terminal-acp-mcp" not in global_state["mcpServers"]

def test_install_builtin_mcp_materializes_json_window_server(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"filesystem": {"command": "echo"}}}),
        encoding="utf-8",
    )

    agent_config_service.install_builtin_mcp_for_agent_window(
        "cursor",
        window_id="window-1",
        source_client_id="client-1",
        source_window_id="window-1",
        server_url="https://control.example.com",
        mcp_token="mcp-token",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "cursor-homes" / "window-1"
    active = json.loads((managed / "mcp.json").read_text(encoding="utf-8"))
    global_active = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    builtin = active["mcpServers"]["web-terminal-acp-mcp"]
    assert builtin["args"] == ["-m", "app.client_agent.web_terminal_acp_mcp"]
    assert builtin["env"]["WEB_TERMINAL_CLIENT_ID"] == "client-1"
    assert builtin["env"]["WEB_TERMINAL_WINDOW_ID"] == "window-1"
    assert builtin["env"]["WEB_TERMINAL_MCP_TOKEN"] == "mcp-token"
    assert "filesystem" in active["mcpServers"]
    assert "web-terminal-acp-mcp" not in global_active["mcpServers"]

def test_system_skill_upload_download_toggle_and_materialize_for_window(tmp_path: Path) -> None:
    config = agent_config_service.install_system_skill_from_zip(
        "review-helper",
        _skill_archive("review-helper", "Review Helper"),
        home=tmp_path,
    )
    skills = section_items(config, "skills")
    assert skills["review-helper"].name == "Review Helper"
    assert skills["review-helper"].enabled is True

    archive = agent_config_service.system_skill_zip_bytes("review-helper", home=tmp_path)
    with zipfile.ZipFile(io.BytesIO(archive)) as downloaded:
        assert "review-helper/SKILL.md" in downloaded.namelist()

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (managed / "skills" / "review-helper" / "SKILL.md").is_file()

    disabled_config = agent_config_service.set_system_agent_config_item_enabled(
        "skills",
        "review-helper",
        False,
        home=tmp_path,
    )
    assert section_items(disabled_config, "skills")["review-helper"].enabled is False
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-2",
        home=tmp_path,
    )
    managed_disabled = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-2"
    assert (managed_disabled / "skills.disabled" / "review-helper" / "SKILL.md").is_file()

def test_system_skill_detail_lists_tree_and_edits_text_file(tmp_path: Path) -> None:
    agent_config_service.install_system_skill_from_zip(
        "review-helper",
        _skill_archive("review-helper", "Review Helper"),
        home=tmp_path,
    )

    detail = agent_config_service.system_skill_detail("review-helper", home=tmp_path)

    assert detail.editable is True
    assert {entry.path for entry in detail.entries} == {"SKILL.md", "scripts", "scripts/run.sh"}
    skill_md = next(file for file in detail.files if file.path == "SKILL.md")
    assert skill_md.content is not None
    assert "Review Helper" in skill_md.content

    updated = agent_config_service.update_system_skill_file(
        "review-helper",
        "scripts/run.sh",
        "echo changed\n",
        home=tmp_path,
    )

    script = next(file for file in updated.files if file.path == "scripts/run.sh")
    assert script.content == "echo changed\n"
    with pytest.raises(ValueError, match="invalid system skill file path"):
        agent_config_service.update_system_skill_file(
            "review-helper",
            "../outside",
            "bad",
            home=tmp_path,
        )

def test_system_builtin_details_are_editable_without_web_terminal_mcp(tmp_path: Path) -> None:
    skill = agent_config_service.system_skill_detail("agent-creator", home=tmp_path)
    assert skill.editable is True
    assert skill.origin == "system_builtin"
    assert skill.overridden is False
    assert {file.path for file in skill.files} == {"SKILL.md", "agents/openai.yaml"}

    with pytest.raises(ValueError, match="system mcp server not found"):
        agent_config_service.system_mcp_detail("web-terminal-acp-mcp", home=tmp_path)

def test_system_builtin_skill_edit_creates_resettable_override(tmp_path: Path) -> None:
    updated = agent_config_service.update_system_skill_file(
        "agent-creator",
        "SKILL.md",
        "---\nname: custom-agent-creator\n---\n",
        home=tmp_path,
    )

    assert updated.origin == "system_config"
    assert updated.overridden is True
    assert updated.editable is True
    assert updated.name == "custom-agent-creator"
    assert updated.files[0].content == "---\nname: custom-agent-creator\n---\n"
    assert section_items(agent_config_service.list_system_agent_config(home=tmp_path), "skills")[
        "agent-creator"
    ].origin == "system_config"

    reset_config = agent_config_service.reset_system_agent_config_item(
        "skills",
        "agent-creator",
        home=tmp_path,
    )
    assert section_items(reset_config, "skills")["agent-creator"].origin == "system_builtin"
    reset_detail = agent_config_service.system_skill_detail("agent-creator", home=tmp_path)
    assert reset_detail.origin == "system_builtin"
    assert reset_detail.overridden is False
    assert "custom-agent-creator" not in (reset_detail.files[0].content or "")

def test_system_builtin_skill_override_materializes_for_agent_windows(tmp_path: Path) -> None:
    agent_config_service.update_system_skill_file(
        "agent-creator",
        "SKILL.md",
        "---\nname: custom-agent-creator\n---\n",
        home=tmp_path,
    )

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (managed / "skills" / "agent-creator" / "SKILL.md").read_text(encoding="utf-8") == (
        "---\nname: custom-agent-creator\n---\n"
    )

    agent_config_service.reset_system_agent_config_item(
        "skills",
        "agent-creator",
        home=tmp_path,
    )
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-2",
        home=tmp_path,
    )
    reset_skill = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "window-2" / "skills" / "agent-creator" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "custom-agent-creator" not in reset_skill

def test_disabled_system_builtin_skill_edit_stays_disabled(tmp_path: Path) -> None:
    agent_config_service.set_system_agent_config_item_enabled(
        "skills",
        "agent-creator",
        False,
        home=tmp_path,
    )

    updated = agent_config_service.update_system_skill_file(
        "agent-creator",
        "SKILL.md",
        "---\nname: disabled-custom-agent-creator\n---\n",
        home=tmp_path,
    )

    assert updated.enabled is False
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    root = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert not (root / "skills" / "agent-creator").exists()
    assert (
        root / "skills.disabled" / "agent-creator" / "SKILL.md"
    ).read_text(encoding="utf-8") == "---\nname: disabled-custom-agent-creator\n---\n"
