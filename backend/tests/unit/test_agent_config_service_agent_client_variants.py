from tests.unit.test_agent_config_service_support import *

def test_claude_config_lists_plugins_hooks_and_updates_settings_json(tmp_path: Path) -> None:
    claude_home = tmp_path / ".claude"
    write_skill(claude_home / "skills", "review")
    (claude_home / "plugins").mkdir(parents=True)
    (claude_home / "plugins" / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "superpowers@superpowers-marketplace": [
                        {"scope": "user", "version": "5.1.0"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (claude_home / "settings.json").write_text(
        json.dumps(
            {
                "enabledPlugins": {"superpowers@superpowers-marketplace": True},
                "hooks": {
                    "beforeShellExecution": [
                        {"command": "hooks/preflight.sh", "matcher": "pytest"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    config = list_agent_config("claude_code", home=tmp_path)

    assert section_items(config, "skills")["review"].enabled is True
    assert section_items(config, "plugins")["superpowers@superpowers-marketplace"].enabled is True
    hooks = section_items(config, "hooks")
    assert hooks["beforeShellExecution:hooks/preflight.sh"].name == "beforeShellExecution"
    assert hooks["beforeShellExecution:hooks/preflight.sh"].enabled is True

    set_agent_config_item_enabled(
        "claude_code",
        "plugins",
        "superpowers@superpowers-marketplace",
        False,
        home=tmp_path,
    )
    settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"]["superpowers@superpowers-marketplace"] is False

def test_codex_config_disables_and_restores_nested_hooks(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "~/.codex/skills/self-improvement/scripts/activator.sh",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    hook_id = "UserPromptSubmit:~/.codex/skills/self-improvement/scripts/activator.sh"
    config = list_agent_config("codex", home=tmp_path)

    assert section_items(config, "hooks")[hook_id].enabled is True

    set_agent_config_item_enabled("codex", "hooks", hook_id, False, home=tmp_path)
    active = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    disabled = json.loads((codex_home / "hooks.disabled.json").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in active["hooks"]
    assert disabled["UserPromptSubmit"][0]["hooks"][0]["command"].endswith("activator.sh")
    assert section_items(list_agent_config("codex", home=tmp_path), "hooks")[hook_id].enabled is False

    set_agent_config_item_enabled("codex", "hooks", hook_id, True, home=tmp_path)
    restored = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    assert restored["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"].endswith("activator.sh")
    assert "enabled" not in restored["hooks"]["UserPromptSubmit"][0]["hooks"][0]

def test_cursor_config_lists_user_skills_and_hooks_json(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    write_skill(cursor_home / "skills-cursor", "canvas")
    write_skill(cursor_home / "skills-cursor.disabled", "loop")
    plugin_manifest = cursor_home / "plugins" / "superpowers" / ".cursor-plugin" / "plugin.json"
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(
        json.dumps(
            {
                "name": "superpowers",
                "displayName": "Superpowers",
            }
        ),
        encoding="utf-8",
    )
    disabled_plugin_manifest = (
        cursor_home
        / "plugins.disabled"
        / "offline"
        / ".cursor-plugin"
        / "plugin.json"
    )
    disabled_plugin_manifest.parent.mkdir(parents=True)
    disabled_plugin_manifest.write_text(
        json.dumps({"name": "offline", "displayName": "Offline Tools"}),
        encoding="utf-8",
    )
    (cursor_home / "hooks.disabled.json").write_text(
        json.dumps(
            {
                "afterFileEdit": [
                    {"command": "hooks/format.sh", "enabled": False}
                ]
            }
        ),
        encoding="utf-8",
    )

    config = list_agent_config("cursor_cli", home=tmp_path)

    assert config.agent == "cursor"
    assert section_items(config, "skills")["canvas"].enabled is True
    assert section_items(config, "skills")["loop"].enabled is False
    assert section_items(config, "plugins")["superpowers"].name == "Superpowers"
    assert section_items(config, "plugins")["superpowers"].enabled is True
    assert section_items(config, "plugins")["offline"].enabled is False
    hook = section_items(config, "hooks")["afterFileEdit:hooks/format.sh"]
    assert hook.name == "afterFileEdit"
    assert hook.enabled is False

    set_agent_config_item_enabled("cursor_cli", "plugins", "offline", True, home=tmp_path)
    assert (cursor_home / "plugins" / "offline" / ".cursor-plugin" / "plugin.json").is_file()
    assert not (cursor_home / "plugins.disabled" / "offline").exists()

    set_agent_config_item_enabled(
        "cursor_cli",
        "hooks",
        "afterFileEdit:hooks/format.sh",
        True,
        home=tmp_path,
    )
    hooks = json.loads((cursor_home / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["hooks"]["afterFileEdit"][0]["command"] == "hooks/format.sh"
    assert "enabled" not in hooks["hooks"]["afterFileEdit"][0]

def test_cursor_plugin_config_uses_directory_id_when_manifest_name_differs(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    plugin_manifest = cursor_home / "plugins.disabled" / "superpowers-dir" / ".cursor-plugin" / "plugin.json"
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(
        json.dumps({"name": "superpowers", "displayName": "Superpowers"}),
        encoding="utf-8",
    )

    config = list_agent_config("cursor_cli", home=tmp_path)

    plugin = section_items(config, "plugins")["superpowers-dir"]
    assert plugin.name == "Superpowers"
    assert plugin.enabled is False

    set_agent_config_item_enabled("cursor_cli", "plugins", "superpowers-dir", True, home=tmp_path)

    assert (cursor_home / "plugins" / "superpowers-dir" / ".cursor-plugin" / "plugin.json").is_file()
    assert not (cursor_home / "plugins.disabled" / "superpowers-dir").exists()

def test_antigravity_config_uses_gemini_antigravity_cli_root(tmp_path: Path) -> None:
    agy_home = tmp_path / ".gemini" / "antigravity-cli"
    write_skill(agy_home / "skills", "browser")
    plugin_manifest = agy_home / "plugins.disabled" / "review" / ".antigravity-plugin" / "plugin.json"
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(
        json.dumps({"name": "review", "displayName": "Review Tools"}),
        encoding="utf-8",
    )
    (agy_home / "hooks.json").write_text(
        json.dumps({"hooks": {"UserPromptSubmit": [{"command": "hooks/audit.sh"}]}}),
        encoding="utf-8",
    )

    config = list_agent_config("agy", home=tmp_path)

    assert config.agent == "antigravity"
    assert section_items(config, "skills")["browser"].enabled is True
    assert section_items(config, "plugins")["review"].name == "Review Tools"
    assert section_items(config, "plugins")["review"].enabled is False
    assert section_items(config, "hooks")["UserPromptSubmit:hooks/audit.sh"].enabled is True

    set_agent_config_item_enabled("antigravity-cli", "plugins", "review", True, home=tmp_path)
    assert (agy_home / "plugins" / "review" / ".antigravity-plugin" / "plugin.json").is_file()
    assert not (agy_home / "plugins.disabled" / "review").exists()

def test_antigravity_window_config_materializes_nested_managed_home_alias(tmp_path: Path) -> None:
    agy_home = tmp_path / ".gemini" / "antigravity-cli"
    write_skill(agy_home / "skills", "browser")
    (agy_home / "settings.json").write_text("{}", encoding="utf-8")
    (agy_home / "antigravity-oauth-token").write_text("token", encoding="utf-8")

    config = agent_config_service.list_window_agent_config(
        "antigravity",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "antigravity-cli-homes" / "window-1"
    command_home = tmp_path / ".web-terminal-acp" / "antigravity-cli-homes" / ".managed-home" / "window-1"
    assert config.agent == "antigravity"
    assert (managed / "settings.json").is_file()
    assert (managed / "skills" / "browser" / "SKILL.md").is_file()
    assert not (managed / "skills").is_symlink()
    assert (managed / "skills" / "browser").is_symlink()
    assert (managed / "skills" / "browser").resolve() == agy_home / "skills" / "browser"
    assert (managed / "antigravity-oauth-token").resolve() == agy_home / "antigravity-oauth-token"
    assert (command_home / ".gemini" / "antigravity-cli").resolve() == managed

def test_agent_client_system_skill_materialization_ignores_empty_system_dir(tmp_path: Path) -> None:
    (tmp_path / ".codex" / "skills" / ".system").mkdir(parents=True)

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (managed / "skills" / ".system").is_dir()
    assert not (managed / "skills.disabled").exists()

def test_agent_client_system_skill_materialization_applies_defaults_per_skill(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills" / ".system", "alpha-disabled")
    write_skill(codex_home / "skills" / ".system", "zeta-enabled")

    agent_config_service.set_system_agent_config_item_enabled(
        "skills",
        "alpha-disabled",
        False,
        home=tmp_path,
    )
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (codex_home / "skills" / ".system" / "alpha-disabled" / "SKILL.md").is_file()
    assert not (managed / "skills" / ".system" / "alpha-disabled").exists()
    assert not (managed / "skills" / ".system").is_symlink()
    assert not (managed / "skills" / "alpha-disabled").exists()
    assert (managed / "skills.disabled" / "alpha-disabled" / "SKILL.md").is_file()
    assert (managed / "skills" / ".system" / "zeta-enabled" / "SKILL.md").is_file()
    assert not (managed / "skills" / "zeta-enabled").exists()
    assert not (managed / "skills.disabled" / "zeta-enabled").exists()

def test_agent_profile_initializes_common_skills_and_agent_md_from_global_home(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills.disabled", "sleepy")
    (codex_home / "AGENTS.md").write_text("Use project rules.\n", encoding="utf-8")

    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )

    profile_root = tmp_path / ".web-terminal-acp" / "agents" / profile.id
    assert profile.name == "Builder"
    assert not (profile_root / "skills" / "docker").exists()
    assert (profile_root / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert (profile_root / "skills.disabled" / "sleepy" / "SKILL.md").is_file()
    assert (profile_root / "AGENT.md").read_text(encoding="utf-8") == "Use project rules.\n"

def test_agent_profile_materializes_common_config_to_agent_client_home(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills.disabled", "sleepy")
    (codex_home / "config.toml").write_text(
        '[plugins."superpowers@openai-curated"]\nenabled = true\n',
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
        "skills",
        "docker",
        False,
        home=tmp_path,
    )
    agent_profile_service.set_agent_profile_config_item_enabled(
        profile.id,
        "codex",
        "skills",
        "sleepy",
        True,
        home=tmp_path,
    )
    agent_profile_service.update_agent_profile(
        profile.id,
        agent_md="Common rules\n",
        home=tmp_path,
    )

    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    profile_root = tmp_path / ".web-terminal-acp" / "agents" / profile.id
    assert (managed / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert (managed / "skills" / "sleepy" / "SKILL.md").is_file()
    assert (managed / "skills.disabled" / "docker").is_symlink()
    assert (managed / "skills.disabled" / "docker").resolve() == profile_root / "skills.disabled" / "docker"
    assert (managed / "skills" / "sleepy").is_symlink()
    assert (managed / "skills" / "sleepy").resolve() == profile_root / "skills" / "sleepy"
    assert (managed / "AGENTS.md").read_text(encoding="utf-8") == "Common rules\n"
    assert (managed / "AGENT.md").read_text(encoding="utf-8") == "Common rules\n"

def test_agent_profile_layers_late_system_skills(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )
    write_skill(codex_home / "skills", "late-global")
    write_skill(tmp_path / ".web-terminal-acp" / "system-config" / "skills", "review-helper")

    config = agent_profile_service.list_agent_profile_config(profile.id, "codex", home=tmp_path)

    skills = section_items(config, "skills")
    assert skills["docker"].enabled is False
    assert skills["review-helper"].enabled is True
    assert skills["review-helper"].origin == "system_config"
    assert "late-global" not in skills

    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (managed / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert (managed / "skills" / "review-helper" / "SKILL.md").is_file()
    assert (managed / "skills" / "review-helper").is_symlink()
    assert (managed / "skills" / "review-helper").resolve() == (
        tmp_path / ".web-terminal-acp" / "system-config" / "skills" / "review-helper"
    )
    assert not (managed / "skills.disabled" / "review-helper").exists()
    assert not (managed / "skills" / "late-global").exists()

    updated = agent_profile_service.set_agent_profile_config_item_enabled(
        profile.id,
        "codex",
        "skills",
        "review-helper",
        False,
        home=tmp_path,
    )
    assert section_items(updated, "skills")["review-helper"].enabled is False

    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-2",
        home=tmp_path,
    )
    managed_disabled = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-2"
    assert (managed_disabled / "skills.disabled" / "review-helper" / "SKILL.md").is_file()

def test_agent_profile_system_config_skill_stays_enabled_when_profile_disabled(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "fuck-my-shit-mountain")
    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )
    profile_root = tmp_path / ".web-terminal-acp" / "agents" / profile.id
    assert (profile_root / "skills.disabled" / "fuck-my-shit-mountain" / "SKILL.md").is_file()
    write_skill(tmp_path / ".web-terminal-acp" / "system-config" / "skills", "fuck-my-shit-mountain")

    config = agent_profile_service.list_agent_profile_config(profile.id, "codex", home=tmp_path)
    assert section_items(config, "skills")["fuck-my-shit-mountain"].enabled is True

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert (managed / "skills" / "fuck-my-shit-mountain" / "SKILL.md").is_file()
    assert not (managed / "skills.disabled" / "fuck-my-shit-mountain").exists()


def test_apply_selection_keeps_system_config_skill_enabled_after_profile_materialization(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "fuck-my-shit-mountain")
    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )
    write_skill(tmp_path / ".web-terminal-acp" / "system-config" / "skills", "fuck-my-shit-mountain")

    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    stale_selection = AgentConfigSelection(
        agent="codex",
        sections=[
            AgentConfigSectionSelection(
                id="skills",
                items=[
                    AgentConfigItemSelection(
                        id="fuck-my-shit-mountain",
                        enabled=False,
                    )
                ],
            )
        ],
    )

    config = agent_config_service.apply_agent_config_selection(
        stale_selection,
        window_id="window-1",
        home=tmp_path,
        protect_system_config_skills=True,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert section_items(config, "skills")["fuck-my-shit-mountain"].enabled is True
    assert (managed / "skills" / "fuck-my-shit-mountain" / "SKILL.md").is_file()
    assert not (managed / "skills.disabled" / "fuck-my-shit-mountain").exists()


def test_apply_selection_can_still_disable_system_config_skill_without_profile_guard(
    tmp_path: Path,
) -> None:
    write_skill(tmp_path / ".web-terminal-acp" / "system-config" / "skills", "review-helper")

    config = agent_config_service.apply_agent_config_selection(
        AgentConfigSelection(
            agent="codex",
            sections=[
                AgentConfigSectionSelection(
                    id="skills",
                    items=[AgentConfigItemSelection(id="review-helper", enabled=False)],
                )
            ],
        ),
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert section_items(config, "skills")["review-helper"].enabled is False
    assert not (managed / "skills" / "review-helper").exists()
    assert (managed / "skills.disabled" / "review-helper" / "SKILL.md").is_file()
