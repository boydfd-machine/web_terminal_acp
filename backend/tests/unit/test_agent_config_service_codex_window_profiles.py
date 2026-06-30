from tests.unit.test_agent_config_service_support import *

from app.contexts.agent_profiles.infrastructure import builtin_profiles

def test_codex_config_lists_user_skills_plugins_and_updates_enablement(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills.disabled", "sleepy")
    plugin_manifest = (
        codex_home
        / "plugins"
        / "cache"
        / "openai-curated"
        / "superpowers"
        / "acdd3141"
        / ".codex-plugin"
        / "plugin.json"
    )
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(
        json.dumps(
            {
                "name": "superpowers",
                "interface": {"displayName": "Superpowers"},
            }
        ),
        encoding="utf-8",
    )
    (codex_home / "config.toml").write_text(
        '[plugins."superpowers@openai-curated"]\nenabled = false\n',
        encoding="utf-8",
    )

    config = list_agent_config("codex", home=tmp_path)

    assert config.agent == "codex"
    assert section_items(config, "skills")["docker"].enabled is True
    assert section_items(config, "skills")["sleepy"].enabled is False
    plugin = section_items(config, "plugins")["superpowers@openai-curated"]
    assert plugin.name == "Superpowers"
    assert plugin.enabled is False

    set_agent_config_item_enabled("codex", "skills", "sleepy", True, home=tmp_path)
    assert (codex_home / "skills" / "sleepy" / "SKILL.md").is_file()
    assert not (codex_home / "skills.disabled" / "sleepy").exists()

    set_agent_config_item_enabled(
        "codex",
        "plugins",
        "superpowers@openai-curated",
        True,
        home=tmp_path,
    )
    assert 'enabled = true' in (codex_home / "config.toml").read_text(encoding="utf-8")

def test_codex_plugin_config_does_not_read_or_rewrite_other_toml_sections(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    plugin_manifest = (
        codex_home
        / "plugins"
        / "cache"
        / "openai-curated"
        / "superpowers"
        / "acdd3141"
        / ".codex-plugin"
        / "plugin.json"
    )
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(json.dumps({"name": "superpowers"}), encoding="utf-8")
    (codex_home / "config.toml").write_text(
        "\n".join(
            [
                '[plugins."superpowers@openai-curated"]',
                "enabled = true",
                "",
                "[profiles.default]",
                "enabled = false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = list_agent_config("codex", home=tmp_path)

    assert section_items(config, "plugins")["superpowers@openai-curated"].enabled is True

    set_agent_config_item_enabled(
        "codex",
        "plugins",
        "superpowers@openai-curated",
        False,
        home=tmp_path,
    )
    updated = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '[plugins."superpowers@openai-curated"]\nenabled = false' in updated
    assert "[profiles.default]\nenabled = false" in updated

def test_apply_agent_config_selection_materializes_per_window_home(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills.disabled", "sleepy")
    (codex_home / "plugins" / "cache").mkdir(parents=True)
    (codex_home / "plugins" / "cache" / "marker").write_text("plugins", encoding="utf-8")
    (codex_home / "config.toml").write_text(
        '[plugins."superpowers@openai-curated"]\nenabled = true\n',
        encoding="utf-8",
    )
    (codex_home / "history.jsonl").write_text('{"prompt":"fix"}\n', encoding="utf-8")

    config = apply_agent_config_selection(
        AgentConfigSelection(
            agent="codex",
            sections=[
                AgentConfigSectionSelection(
                    id="skills",
                    items=[
                        AgentConfigItemSelection(id="docker", enabled=False),
                        AgentConfigItemSelection(id="sleepy", enabled=True),
                    ],
                ),
                AgentConfigSectionSelection(
                    id="plugins",
                    items=[
                        AgentConfigItemSelection(id="superpowers@openai-curated", enabled=False),
                    ],
                ),
            ],
        ),
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert config.agent == "codex"
    assert (managed / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert (managed / "skills" / "sleepy" / "SKILL.md").is_file()
    assert not (managed / "skills").is_symlink()
    assert not (managed / "skills.disabled").is_symlink()
    assert (managed / "skills.disabled" / "docker").is_symlink()
    assert (managed / "skills.disabled" / "docker").resolve() == codex_home / "skills" / "docker"
    assert (managed / "skills" / "sleepy").is_symlink()
    assert (managed / "skills" / "sleepy").resolve() == codex_home / "skills.disabled" / "sleepy"
    assert not (managed / "plugins").is_symlink()
    assert (managed / "plugins" / "cache").is_symlink()
    assert (managed / "plugins" / "cache").resolve() == codex_home / "plugins" / "cache"
    assert (managed / ".tmp").is_symlink()
    assert (managed / ".tmp").resolve() == tmp_path / ".web-terminal-acp" / "shared-cache" / "codex" / "tmp"
    assert 'enabled = false' in (managed / "config.toml").read_text(encoding="utf-8")
    assert (managed / "history.jsonl").resolve() == codex_home / "history.jsonl"
    assert (codex_home / "skills" / "docker" / "SKILL.md").is_file()
    assert (codex_home / "skills.disabled" / "sleepy" / "SKILL.md").is_file()

def test_apply_agent_config_selection_skips_broken_user_skill_symlink(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    (codex_home / "skills" / "missing-skill").symlink_to(tmp_path / "deleted-source")

    config = apply_agent_config_selection(
        AgentConfigSelection(agent="codex", sections=[]),
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert section_items(config, "skills")["docker"].enabled is True
    assert (managed / "skills" / "docker" / "SKILL.md").is_file()
    assert not (managed / "skills" / "missing-skill").exists()
    assert not (managed / "skills" / "missing-skill").is_symlink()

def test_list_window_agent_config_reads_existing_managed_home(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills", "review")
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    write_skill(managed / "skills.disabled", "docker")

    config = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    assert section_items(config, "skills")["docker"].enabled is False
    assert section_items(config, "skills")["review"].enabled is True


def test_list_window_agent_config_adds_new_system_config_disabled_skill(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")

    first_config = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    assert "image-to-ppt" not in section_items(first_config, "skills")

    write_skill(
        tmp_path / ".web-terminal-acp" / "system-config" / "skills.disabled",
        "image-to-ppt",
    )

    config = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    image_to_ppt = section_items(config, "skills")["image-to-ppt"]
    assert image_to_ppt.enabled is False
    assert image_to_ppt.origin == "client"
    assert image_to_ppt.path is not None
    assert Path(image_to_ppt.path).resolve() == (
        tmp_path
        / ".web-terminal-acp"
        / "system-config"
        / "skills.disabled"
        / "image-to-ppt"
    )


def test_list_window_agent_config_preserves_window_system_skill_toggle(
    tmp_path: Path,
) -> None:
    write_skill(
        tmp_path / ".web-terminal-acp" / "system-config" / "skills.disabled",
        "image-to-ppt",
    )

    initial = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    assert section_items(initial, "skills")["image-to-ppt"].enabled is False

    toggled = agent_config_service.set_window_agent_config_item_enabled(
        "codex",
        "skills",
        "image-to-ppt",
        True,
        window_id="window-1",
        home=tmp_path,
    )
    assert section_items(toggled, "skills")["image-to-ppt"].enabled is True

    config = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    assert section_items(config, "skills")["image-to-ppt"].enabled is True


def test_set_window_agent_config_detaches_shell_symlinked_skill_config(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    (codex_home / "skills.disabled").mkdir(parents=True)
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    managed.mkdir(parents=True)
    (managed / "skills").symlink_to(codex_home / "skills")
    (managed / "skills.disabled").symlink_to(codex_home / "skills.disabled")

    config = agent_config_service.set_window_agent_config_item_enabled(
        "codex",
        "skills",
        "docker",
        False,
        window_id="window-1",
        home=tmp_path,
    )

    assert section_items(config, "skills")["docker"].enabled is False
    assert not (managed / "skills").is_symlink()
    assert not (managed / "skills.disabled").is_symlink()
    assert (managed / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert (codex_home / "skills" / "docker" / "SKILL.md").is_file()
    assert not (codex_home / "skills.disabled" / "docker").exists()


def test_list_window_agent_config_migrates_legacy_root_skill_symlink(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    managed.mkdir(parents=True)
    (managed / "skills").symlink_to(codex_home / "skills")

    config = agent_config_service.list_window_agent_config(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    assert section_items(config, "skills")["docker"].enabled is True
    assert not (managed / "skills").is_symlink()
    assert (managed / "skills" / "docker").is_symlink()
    assert (managed / "skills" / "docker").resolve() == codex_home / "skills" / "docker"
    assert (codex_home / "skills" / "docker" / "SKILL.md").is_file()


def test_set_window_agent_config_detaches_shell_symlinked_codex_plugin_config(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    plugin_manifest = (
        codex_home
        / "plugins"
        / "cache"
        / "openai-curated"
        / "superpowers"
        / "acdd3141"
        / ".codex-plugin"
        / "plugin.json"
    )
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text(json.dumps({"name": "superpowers"}), encoding="utf-8")
    (codex_home / "config.toml").write_text(
        '[plugins."superpowers@openai-curated"]\nenabled = true\n',
        encoding="utf-8",
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    managed.mkdir(parents=True)
    (managed / "plugins").symlink_to(codex_home / "plugins")
    (managed / "config.toml").symlink_to(codex_home / "config.toml")

    config = agent_config_service.set_window_agent_config_item_enabled(
        "codex",
        "plugins",
        "superpowers@openai-curated",
        False,
        window_id="window-1",
        home=tmp_path,
    )

    assert section_items(config, "plugins")["superpowers@openai-curated"].enabled is False
    assert not (managed / "config.toml").is_symlink()
    assert 'enabled = false' in (managed / "config.toml").read_text(encoding="utf-8")
    assert 'enabled = true' in (codex_home / "config.toml").read_text(encoding="utf-8")

def test_apply_agent_config_selection_links_history_for_claude_and_cursor(tmp_path: Path) -> None:
    claude_home = tmp_path / ".claude"
    cursor_home = tmp_path / ".cursor"
    claude_home.mkdir()
    cursor_home.mkdir()
    (claude_home / "history.jsonl").write_text('{"display":"fix"}\n', encoding="utf-8")
    (claude_home / "file-history").mkdir()
    (cursor_home / "chats").mkdir()
    (cursor_home / "chats" / "marker").write_text("cursor chat", encoding="utf-8")

    apply_agent_config_selection(
        AgentConfigSelection(agent="claude", sections=[]),
        window_id="window-1",
        home=tmp_path,
    )
    apply_agent_config_selection(
        AgentConfigSelection(agent="cursor", sections=[]),
        window_id="window-1",
        home=tmp_path,
    )

    managed_claude = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    managed_cursor = tmp_path / ".web-terminal-acp" / "cursor-homes" / "window-1"
    assert (managed_claude / "history.jsonl").resolve() == claude_home / "history.jsonl"
    assert (managed_claude / "file-history").resolve() == claude_home / "file-history"
    assert (managed_cursor / "chats").resolve() == cursor_home / "chats"

def test_directory_config_rejects_path_traversal_item_id(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")

    with pytest.raises(ValueError, match="invalid config item id"):
        set_agent_config_item_enabled("codex", "skills", "../escape", False, home=tmp_path)

    assert (codex_home / "skills" / "docker" / "SKILL.md").is_file()
    assert not (tmp_path / "escape").exists()

def test_codex_plugin_config_rejects_unsafe_toml_item_id(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    unsafe_ids = [
        'safe"]\nenabled = true\n[plugins."injected',
        r"marketplace\plugin",
    ]
    for item_id in unsafe_ids:
        with pytest.raises(ValueError, match="invalid config item id"):
            set_agent_config_item_enabled(
                "codex",
                "plugins",
                item_id,
                False,
                home=tmp_path,
            )

    assert not (codex_home / "config.toml").exists()

def test_claude_plugin_config_rejects_control_character_item_id(tmp_path: Path) -> None:
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()

    with pytest.raises(ValueError, match="invalid config item id"):
        set_agent_config_item_enabled(
            "claude",
            "plugins",
            "unsafe\x00plugin",
            False,
            home=tmp_path,
        )

    assert not (claude_home / "settings.json").exists()

def test_claude_plugin_config_concurrent_updates_preserve_distinct_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()
    (claude_home / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"one": True, "two": True}}),
        encoding="utf-8",
    )
    first_write_started = Event()
    release_first_write = Event()
    second_write_started = Event()
    original_write = agent_config_service._write_text_file_atomic
    delayed = False

    def slow_first_write(path: Path, content: str) -> None:
        nonlocal delayed
        if path == claude_home / "settings.json":
            if not delayed:
                delayed = True
                first_write_started.set()
                assert release_first_write.wait(timeout=5)
            else:
                second_write_started.set()
        original_write(path, content)

    monkeypatch.setattr(agent_config_service, "_write_text_file_atomic", slow_first_write)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(
            set_agent_config_item_enabled,
            "claude",
            "plugins",
            "one",
            False,
            home=tmp_path,
        )
        assert first_write_started.wait(timeout=5)
        future_two = executor.submit(
            set_agent_config_item_enabled,
            "claude",
            "plugins",
            "two",
            False,
            home=tmp_path,
        )
        assert not second_write_started.wait(timeout=0.2)
        release_first_write.set()
        future_one.result()
        future_two.result()

    settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"] == {"one": False, "two": False}

def test_agent_profile_config_concurrent_updates_preserve_distinct_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude_home = tmp_path / ".claude"
    (claude_home / "settings.json").parent.mkdir(parents=True)
    (claude_home / "plugins").mkdir(parents=True)
    (claude_home / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"one": [], "two": []}}),
        encoding="utf-8",
    )
    (claude_home / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"one": True, "two": True}}),
        encoding="utf-8",
    )
    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="claude",
        home=tmp_path,
    )
    profile_manifest = tmp_path / ".web-terminal-acp" / "agents" / profile.id / "profile.json"
    first_write_started = Event()
    release_first_write = Event()
    second_write_started = Event()
    original_write = agent_config_service._write_text_file_atomic
    delayed = False

    def slow_first_write(path: Path, content: str) -> None:
        nonlocal delayed
        if path == profile_manifest:
            if not delayed:
                delayed = True
                first_write_started.set()
                assert release_first_write.wait(timeout=5)
            else:
                second_write_started.set()
        original_write(path, content)

    monkeypatch.setattr(agent_config_service, "_write_text_file_atomic", slow_first_write)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(
            agent_profile_service.set_agent_profile_config_item_enabled,
            profile.id,
            "claude",
            "plugins",
            "one",
            False,
            home=tmp_path,
        )
        assert first_write_started.wait(timeout=5)
        future_two = executor.submit(
            agent_profile_service.set_agent_profile_config_item_enabled,
            profile.id,
            "claude",
            "plugins",
            "two",
            False,
            home=tmp_path,
        )
        assert not second_write_started.wait(timeout=0.2)
        release_first_write.set()
        future_one.result()
        future_two.result()

    config = agent_profile_service.list_agent_profile_config(profile.id, "claude", home=tmp_path)
    plugins = section_items(config, "plugins")
    assert plugins["one"].enabled is False
    assert plugins["two"].enabled is False

def test_new_agent_profile_starts_with_no_enabled_skills_or_mcp(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    write_skill(codex_home / "skills.disabled", "sleepy")
    (codex_home / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\n',
        encoding="utf-8",
    )
    write_skill(
        tmp_path / ".web-terminal-acp" / "system-config" / "skills",
        "review-helper",
    )
    agent_config_service.upsert_system_mcp_server(
        "global-research",
        {"command": "echo"},
        home=tmp_path,
    )

    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )
    config_toml = codex_home / "config.toml"
    config_toml.write_text(
        config_toml.read_text(encoding="utf-8")
        + '\n[mcp_servers.late-filesystem]\ncommand = "pwd"\n',
        encoding="utf-8",
    )
    agent_config_service.upsert_system_mcp_server(
        "late-research",
        {"command": "pwd"},
        home=tmp_path,
    )

    config = agent_profile_service.list_agent_profile_config(
        profile.id,
        "codex",
        home=tmp_path,
    )
    skills = section_items(config, "skills")
    mcp = section_items(config, "mcp")
    assert {"docker", "sleepy", "review-helper"}.issubset(skills)
    assert {"filesystem", "global-research", "late-filesystem", "late-research"}.issubset(mcp)
    assert [item.id for item in skills.values() if item.enabled] == ["review-helper"]
    assert [item.id for item in mcp.values() if item.enabled] == []

def test_builtin_developer_profile_materializes_managed_codex_home(tmp_path: Path) -> None:
    config = builtin_profiles.materialize_builtin_profile_for_window(
        "builtin/developer",
        "codex",
        window_id="window-developer",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-developer"
    assert config is not None
    assert (managed / "AGENTS.md").read_text(encoding="utf-8").startswith("# Built-in Developer Agent")
    assert (managed / "AGENT.md").read_text(encoding="utf-8").startswith("# Built-in Developer Agent")
    assert (managed / "skills" / "frontend-development" / "SKILL.md").is_file()
    assert (managed / "skills" / "backend-development" / "SKILL.md").is_file()
    assert (managed / "skills" / "tdd" / "SKILL.md").is_file()
    assert (managed / "skills" / "deep-research" / "SKILL.md").is_file()
    assert section_items(config, "skills")["frontend-development"].enabled is True
