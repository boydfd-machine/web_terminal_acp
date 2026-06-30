import json
from pathlib import Path

from app.contexts.agent_profiles.infrastructure import agent_config_store
from app.contexts.agent_profiles.infrastructure import profile_store


def section_items(config, section: str):
    for candidate in config.sections:
        if candidate.id == section:
            return {item.id: item for item in candidate.items}
    raise AssertionError(f"missing section: {section}")


def write_codex_plugin(home: Path, name: str, marketplace: str, *, enabled: bool) -> str:
    plugin_id = f"{name}@{marketplace}"
    manifest = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / marketplace
        / name
        / "acdd3141"
        / ".codex-plugin"
        / "plugin.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": name, "interface": {"displayName": "Superpowers"}}),
        encoding="utf-8",
    )
    (home / ".codex" / "config.toml").write_text(
        f'[plugins."{plugin_id}"]\nenabled = {"true" if enabled else "false"}\n',
        encoding="utf-8",
    )
    return plugin_id


def write_claude_plugin(home: Path, plugin_id: str, *, enabled: bool) -> None:
    claude_home = home / ".claude"
    (claude_home / "plugins").mkdir(parents=True)
    (claude_home / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": {plugin_id: [{"scope": "user"}]}}),
        encoding="utf-8",
    )
    (claude_home / "settings.json").write_text(
        json.dumps({"enabledPlugins": {plugin_id: enabled}}),
        encoding="utf-8",
    )


def write_directory_plugin(
    root: Path,
    plugin_id: str,
    *,
    marker: str,
    display_name: str,
    enabled: bool,
) -> None:
    base = root / ("plugins" if enabled else "plugins.disabled") / plugin_id
    manifest = base / marker / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": plugin_id, "displayName": display_name}),
        encoding="utf-8",
    )


def test_system_agent_config_lists_plugins_from_all_agent_cli_roots(tmp_path: Path) -> None:
    codex_plugin = write_codex_plugin(
        tmp_path,
        "superpowers",
        "openai-curated",
        enabled=True,
    )
    write_claude_plugin(
        tmp_path,
        "superpowers@superpowers-marketplace",
        enabled=False,
    )
    write_directory_plugin(
        tmp_path / ".cursor",
        "cursor-review",
        marker=".cursor-plugin",
        display_name="Cursor Review",
        enabled=True,
    )
    write_directory_plugin(
        tmp_path / ".gemini" / "antigravity-cli",
        "agy-review",
        marker=".antigravity-plugin",
        display_name="Agy Review",
        enabled=False,
    )

    config = agent_config_store.list_system_agent_config(home=tmp_path)

    plugins = section_items(config, "plugins")
    assert plugins[f"codex:{codex_plugin}"].name == "Codex / Superpowers"
    assert plugins[f"codex:{codex_plugin}"].enabled is True
    assert plugins["claude:superpowers@superpowers-marketplace"].name == (
        "Claude Code / superpowers@superpowers-marketplace"
    )
    assert plugins["claude:superpowers@superpowers-marketplace"].enabled is False
    assert plugins["cursor:cursor-review"].name == "Cursor / Cursor Review"
    assert plugins["cursor:cursor-review"].enabled is True
    assert plugins["antigravity:agy-review"].name == "Antigravity CLI / Agy Review"
    assert plugins["antigravity:agy-review"].enabled is False


def test_system_plugin_default_materializes_to_agent_window_native_config(tmp_path: Path) -> None:
    codex_plugin = write_codex_plugin(
        tmp_path,
        "superpowers",
        "openai-curated",
        enabled=True,
    )
    write_directory_plugin(
        tmp_path / ".cursor",
        "cursor-review",
        marker=".cursor-plugin",
        display_name="Cursor Review",
        enabled=False,
    )

    agent_config_store.set_system_agent_config_item_enabled(
        "plugins",
        f"codex:{codex_plugin}",
        False,
        home=tmp_path,
    )
    agent_config_store.set_system_agent_config_item_enabled(
        "plugins",
        "cursor:cursor-review",
        True,
        home=tmp_path,
    )

    agent_config_store.apply_agent_config_selection(
        agent_config_store.AgentConfigSelection(agent="codex", sections=[]),
        window_id="window-codex",
        home=tmp_path,
    )
    agent_config_store.apply_agent_config_selection(
        agent_config_store.AgentConfigSelection(agent="cursor", sections=[]),
        window_id="window-cursor",
        home=tmp_path,
    )

    managed_codex = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-codex"
    managed_cursor = tmp_path / ".web-terminal-acp" / "cursor-homes" / "window-cursor"
    assert f'[plugins."{codex_plugin}"]\nenabled = false' in (
        managed_codex / "config.toml"
    ).read_text(encoding="utf-8")
    assert (
        managed_cursor
        / "plugins"
        / "cursor-review"
        / ".cursor-plugin"
        / "plugin.json"
    ).is_file()
    assert not (managed_cursor / "plugins.disabled" / "cursor-review").exists()


def test_agent_profile_plugin_config_defaults_to_system_plugin_setting(
    tmp_path: Path,
) -> None:
    codex_plugin = write_codex_plugin(
        tmp_path,
        "superpowers",
        "openai-curated",
        enabled=True,
    )
    profile = profile_store.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )

    agent_config_store.set_system_agent_config_item_enabled(
        "plugins",
        f"codex:{codex_plugin}",
        False,
        home=tmp_path,
    )

    config = profile_store.list_agent_profile_config(profile.id, "codex", home=tmp_path)
    assert section_items(config, "plugins")[codex_plugin].enabled is False

    updated = profile_store.set_agent_profile_config_item_enabled(
        profile.id,
        "codex",
        "plugins",
        codex_plugin,
        True,
        home=tmp_path,
    )
    assert section_items(updated, "plugins")[codex_plugin].enabled is True

    profile_store.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert f'[plugins."{codex_plugin}"]\nenabled = true' in (
        managed / "config.toml"
    ).read_text(encoding="utf-8")
