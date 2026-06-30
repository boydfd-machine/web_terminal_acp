# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

import json

def test_agent_environment_prepares_per_window_agent_config_links(tmp_path) -> None:
    home = tmp_path
    (home / ".claude.json").write_text("{}", encoding="utf-8")
    source_items = {
        ".codex": [
            "auth.json",
            "config.toml",
            "hooks",
            "hooks.json",
            "hooks.disabled.json",
            "AGENTS.md",
            "skills",
            "skills.disabled",
            "plugins",
            "plugins.disabled",
            "plugin_marketplaces.json",
            "history.jsonl",
        ],
        ".claude": [
            "settings.json",
            "settings.local.json",
            "commands",
            "hooks",
            "hooks.disabled.json",
            "plugins",
            "plugins.disabled",
            "skills",
            "skills.disabled",
            "api-key-helper.sh",
            "history.jsonl",
        ],
        ".cursor": [
            "agent-cli-state.json",
            "cli-config.json",
            "hooks",
            "hooks.json",
            "hooks.disabled.json",
            "plugins",
            "plugins.disabled",
            "skills-cursor",
            "skills-cursor.disabled",
            "history.jsonl",
        ],
        ".gemini/antigravity-cli": [
            "settings.json",
            "keybindings.json",
            "hooks",
            "hooks.json",
            "hooks.disabled.json",
            "plugins",
            "plugins.disabled",
            "skills",
            "skills.disabled",
            "history.jsonl",
            "antigravity-oauth-token",
            "installation_id",
            "brain",
            "cache",
            "log",
            "scratch",
        ],
    }
    directory_names = {
        ".codex": {"hooks", "skills", "skills.disabled", "plugins", "plugins.disabled"},
        ".claude": {"commands", "hooks", "plugins", "plugins.disabled", "skills", "skills.disabled"},
        ".cursor": {"hooks", "plugins", "plugins.disabled", "skills-cursor", "skills-cursor.disabled"},
        ".gemini/antigravity-cli": {
            "hooks",
            "plugins",
            "plugins.disabled",
            "skills",
            "skills.disabled",
            "brain",
            "cache",
            "log",
            "scratch",
        },
    }
    for root_name, item_names in source_items.items():
        root = home / root_name
        root.mkdir(parents=True)
        for item_name in item_names:
            path = root / item_name
            if item_name in directory_names[root_name]:
                path.mkdir()
                (path / "marker").write_text(item_name, encoding="utf-8")
                if item_name in {
                    "skills",
                    "skills.disabled",
                    "skills-cursor",
                    "skills-cursor.disabled",
                    "plugins",
                    "plugins.disabled",
                }:
                    child = path / f"{item_name}-child"
                    child.mkdir()
                    (child / "marker").write_text(f"{item_name}-child", encoding="utf-8")
                    (path / f"{item_name}.json").write_text(
                        f"{item_name}-file",
                        encoding="utf-8",
                    )
            else:
                path.write_text("{}", encoding="utf-8")
    (home / ".claude" / "file-history").mkdir()
    (home / ".claude" / "file-history" / "marker").write_text("file-history", encoding="utf-8")
    (home / ".cursor" / "chats").mkdir()
    (home / ".cursor" / "chats" / "marker").write_text("chats", encoding="utf-8")
    (home / ".gemini" / "antigravity-cli" / "cache" / "onboarding.json").write_text('{"theme": "dark", "agreed": true}', encoding="utf-8")

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-1",
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-1",
        "WEB_TERMINAL_ORIGINAL_CLAUDE_JSON": "~/.claude.json",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_HOME": "~/.web-terminal-acp/antigravity-cli-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME": "~/.web-terminal-acp/antigravity-cli-homes/.managed-home/window-1",
        "WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME": "~/.gemini/antigravity-cli",
        "WEB_TERMINAL_ORIGINAL_HOME": "~",
        "CODEX_HOME": "",
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"{_agent_environment_script()}\n"
            "__web_terminal_prepare_codex_home\n"
            "__web_terminal_prepare_claude_code_home\n"
            "__web_terminal_prepare_cursor_home\n"
            "__web_terminal_prepare_antigravity_home\n",
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    codex_home = home / ".web-terminal-acp" / "codex-homes" / "window-1"
    claude_home = home / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    antigravity_home = home / ".web-terminal-acp" / "antigravity-cli-homes" / "window-1"
    antigravity_command_home = (
        home / ".web-terminal-acp" / "antigravity-cli-homes" / ".managed-home" / "window-1"
    )

    assert (codex_home / "sessions").is_dir()
    assert (codex_home / "log").is_dir()
    assert (codex_home / "shell_snapshots").is_dir()
    assert (codex_home / ".tmp").is_symlink()
    assert (codex_home / ".tmp").resolve() == (
        home / ".web-terminal-acp" / "shared-cache" / "codex" / "tmp"
    )
    assert (claude_home / "projects").is_dir()
    assert (cursor_home / "chats").is_dir()
    assert antigravity_home.is_dir()
    assert (antigravity_command_home / ".gemini" / "antigravity-cli").resolve() == antigravity_home
    assert (home / ".web-terminal-acp" / "shared-cache" / "antigravity").is_dir()
    assert not (cursor_home / "chats").is_symlink()
    assert not (cursor_home / "chats" / "marker").exists()

    for item_name in source_items[".codex"]:
        if item_name == "config.toml":
            continue
        if item_name in {"skills", "skills.disabled", "plugins", "plugins.disabled"}:
            target_root = codex_home / item_name
            assert target_root.is_dir()
            assert not target_root.is_symlink()
            child = target_root / f"{item_name}-child"
            assert child.is_symlink()
            assert child.resolve() == home / ".codex" / item_name / f"{item_name}-child"
            copied_file = target_root / f"{item_name}.json"
            assert copied_file.is_file()
            assert not copied_file.is_symlink()
            assert copied_file.read_text(encoding="utf-8") == f"{item_name}-file"
            continue
        assert (codex_home / item_name).resolve() == home / ".codex" / item_name
    # The Codex trust marker breaks the config.toml symlink into an independent
    # copy so per-window projects[cwd] trust entries do not leak globally.
    managed_codex_config = codex_home / "config.toml"
    assert managed_codex_config.exists()
    assert not managed_codex_config.is_symlink()
    assert "[projects." in managed_codex_config.read_text(encoding="utf-8")
    assert (home / ".codex" / "config.toml").read_text(encoding="utf-8") == "{}"
    for item_name in source_items[".claude"]:
        if item_name in {"skills", "skills.disabled", "plugins", "plugins.disabled"}:
            target_root = claude_home / item_name
            assert target_root.is_dir()
            assert not target_root.is_symlink()
            child = target_root / f"{item_name}-child"
            assert child.is_symlink()
            assert child.resolve() == home / ".claude" / item_name / f"{item_name}-child"
            copied_file = target_root / f"{item_name}.json"
            assert copied_file.is_file()
            assert not copied_file.is_symlink()
            assert copied_file.read_text(encoding="utf-8") == f"{item_name}-file"
            continue
        assert (claude_home / item_name).resolve() == home / ".claude" / item_name
    # The trust marker breaks the .claude.json symlink into an independent copy so
    # the per-window projects[cwd] trust entry does not leak into the user's global
    # config. The remaining agent-home items stay symlinked to the user source.
    managed_claude_json = claude_home / ".claude.json"
    assert managed_claude_json.exists()
    assert not managed_claude_json.is_symlink()
    assert managed_claude_json.read_text(encoding="utf-8") != "{}"
    assert (home / ".claude.json").read_text(encoding="utf-8") == "{}"
    assert (claude_home / "file-history").resolve() == home / ".claude" / "file-history"
    for item_name in source_items[".cursor"]:
        if item_name in {"skills-cursor", "skills-cursor.disabled"}:
            target_root = cursor_home / item_name
            assert target_root.is_dir()
            assert not target_root.is_symlink()
            continue
        if item_name in {"plugins", "plugins.disabled"}:
            target_root = cursor_home / item_name
            assert target_root.is_dir()
            assert not target_root.is_symlink()
            child = target_root / f"{item_name}-child"
            assert child.is_symlink()
            assert child.resolve() == home / ".cursor" / item_name / f"{item_name}-child"
            copied_file = target_root / f"{item_name}.json"
            assert copied_file.is_file()
            assert not copied_file.is_symlink()
            assert copied_file.read_text(encoding="utf-8") == f"{item_name}-file"
            continue
        if item_name == "cli-config.json":
            managed_cursor_config = cursor_home / "cli-config.json"
            assert managed_cursor_config.is_file()
            assert not managed_cursor_config.is_symlink()
            cursor_config = json.loads(managed_cursor_config.read_text(encoding="utf-8"))
            assert cursor_config["statusLine"]["command"] == str(
                cursor_home / "bin" / "cursor-statusline-writer.sh"
            )
            continue
        assert (cursor_home / item_name).resolve() == home / ".cursor" / item_name
    cursor_writer = cursor_home / "bin" / "cursor-statusline-writer.sh"
    assert cursor_writer.is_file()
    assert cursor_writer.stat().st_mode & 0o111
    skill_overlay = cursor_home / "skill-home"
    assert skill_overlay.is_dir()
    assert (skill_overlay / ".cursor" / "skills-cursor").resolve() == cursor_home / "skills-cursor"
    assert (skill_overlay / ".claude" / "skills").is_dir()
    assert list((skill_overlay / ".claude" / "skills").iterdir()) == []
    for item_name in source_items[".gemini/antigravity-cli"]:
        target = antigravity_home / item_name
        if item_name in {"brain", "log", "scratch"}:
            assert not target.exists()
        elif item_name == "cache":
            assert target.is_dir()
            assert not (target / "marker").exists()
            assert (target / "onboarding.json").read_text(encoding="utf-8") == '{"theme": "dark", "agreed": true}'
        elif item_name in {"skills", "skills.disabled", "plugins", "plugins.disabled"}:
            assert target.is_dir()
            assert not target.is_symlink()
            child = target / f"{item_name}-child"
            assert child.is_symlink()
            assert child.resolve() == (
                home / ".gemini" / "antigravity-cli" / item_name / f"{item_name}-child"
            )
            copied_file = target / f"{item_name}.json"
            assert copied_file.is_file()
            assert not copied_file.is_symlink()
            assert copied_file.read_text(encoding="utf-8") == f"{item_name}-file"
        else:
            assert target.resolve() == home / ".gemini" / "antigravity-cli" / item_name

def test_prepare_cursor_home_skips_existing_home_without_reinitializing_links(tmp_path) -> None:
    home = tmp_path / "home"
    source_chats = home / ".cursor" / "chats"
    source_chats.mkdir(parents=True)
    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    cursor_home.mkdir(parents=True)
    (cursor_home / "chats").symlink_to(source_chats)

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-1",
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-1",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_HOME": "~/.web-terminal-acp/antigravity-cli-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME": "~/.web-terminal-acp/antigravity-cli-homes/.managed-home/window-1",
        "CODEX_HOME": "",
    }
    result = subprocess.run(
        ["bash", "-c", f"{_agent_environment_script()}\n__web_terminal_prepare_cursor_home\n"],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (cursor_home / "chats").is_dir()
    assert not (cursor_home / "chats").is_symlink()

def test_prepare_cursor_home_repairs_root_state_links_for_existing_home(tmp_path) -> None:
    home = tmp_path / "home"
    source_cursor = home / ".cursor"
    source_cursor.mkdir(parents=True)
    (source_cursor / "1").write_text("", encoding="utf-8")
    (source_cursor / "managed").mkdir()
    cursor_home = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    cursor_home.mkdir(parents=True)

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
        "WEB_TERMINAL_ORIGINAL_CURSOR_DIR": "~/.cursor",
    }
    result = subprocess.run(
        ["bash", "-c", f"{_agent_environment_script()}\n__web_terminal_prepare_cursor_home\n"],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (cursor_home / "1").resolve() == source_cursor / "1"
    assert (cursor_home / "managed").resolve() == source_cursor / "managed"
    overlay_cursor = cursor_home / "skill-home" / ".cursor"
    assert (overlay_cursor / "1").resolve() == source_cursor / "1"
    assert (overlay_cursor / "managed").resolve() == source_cursor / "managed"

def test_agent_environment_allows_client_without_agent_installs_under_zsh(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-1",
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-1",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_HOME": "~/.web-terminal-acp/antigravity-cli-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME": "~/.web-terminal-acp/antigravity-cli-homes/.managed-home/window-1",
        "CODEX_HOME": "",
    }
    result = subprocess.run(
        [
            "zsh",
            "-c",
            f"{_agent_environment_script()}\n"
            "__web_terminal_prepare_codex_home\n"
            "__web_terminal_prepare_claude_code_home\n"
            "__web_terminal_prepare_cursor_home\n"
            "__web_terminal_prepare_antigravity_home\n",
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert (home / ".web-terminal-acp" / "codex-homes" / "window-1" / "sessions").is_dir()
    assert (home / ".web-terminal-acp" / "claude-code-homes" / "window-1" / "projects").is_dir()
    assert (home / ".web-terminal-acp" / "cursor-homes" / "window-1" / "chats").is_dir()
    assert (home / ".web-terminal-acp" / "antigravity-cli-homes" / "window-1").is_dir()


def _run_prepare_claude_code_home(home, cwd, claude_json_contents=None):
    if claude_json_contents is not None:
        (home / ".claude.json").write_text(json.dumps(claude_json_contents), encoding="utf-8")
    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-trust",
        "WEB_TERMINAL_ORIGINAL_CLAUDE_JSON": "~/.claude.json",
    }
    result = subprocess.run(
        ["bash", "-c", f"{_agent_environment_script()}\n__web_terminal_prepare_claude_code_home\n"],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
    )
    return result


def test_prepare_claude_code_home_marks_cwd_as_trusted(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()

    result = _run_prepare_claude_code_home(home, target_cwd, claude_json_contents={})
    assert result.returncode == 0, result.stderr

    managed_json = home / ".web-terminal-acp" / "claude-code-homes" / "window-trust" / ".claude.json"
    data = json.loads(managed_json.read_text(encoding="utf-8"))
    target_real = str(target_cwd.resolve())
    assert target_real in data["projects"]
    entry = data["projects"][target_real]
    assert entry["hasTrustDialogAccepted"] is True
    assert entry["projectOnboardingSeenCount"] == 1


def test_prepare_claude_code_home_breaks_symlink_to_protect_global_config(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    original_data = {"projects": {"/existing/path": {"hasTrustDialogAccepted": False}}}
    (home / ".claude.json").write_text(json.dumps(original_data), encoding="utf-8")
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    target_real = str(target_cwd.resolve())

    result = _run_prepare_claude_code_home(home, target_cwd)
    assert result.returncode == 0, result.stderr

    managed_json = home / ".web-terminal-acp" / "claude-code-homes" / "window-trust" / ".claude.json"
    assert managed_json.exists()
    assert not managed_json.is_symlink()

    managed_data = json.loads(managed_json.read_text(encoding="utf-8"))
    assert managed_data["projects"][target_real]["hasTrustDialogAccepted"] is True
    assert "/existing/path" in managed_data["projects"]

    original_after = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert target_real not in original_after["projects"]
    assert list(original_after["projects"].keys()) == ["/existing/path"]


def test_prepare_claude_code_home_preserves_existing_trusted_entries(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    target_real = str(target_cwd.resolve())
    other = "/some/other/path"
    seed = {"projects": {other: {"hasTrustDialogAccepted": True, "projectOnboardingSeenCount": 5}}}

    result = _run_prepare_claude_code_home(home, target_cwd, claude_json_contents=seed)
    assert result.returncode == 0, result.stderr

    managed_json = home / ".web-terminal-acp" / "claude-code-homes" / "window-trust" / ".claude.json"
    data = json.loads(managed_json.read_text(encoding="utf-8"))
    assert data["projects"][other]["hasTrustDialogAccepted"] is True
    assert data["projects"][other]["projectOnboardingSeenCount"] == 5
    assert data["projects"][target_real]["hasTrustDialogAccepted"] is True


def test_prepare_claude_code_home_is_idempotent_when_already_trusted(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    target_real = str(target_cwd.resolve())
    seed = {
        "projects": {
            target_real: {"hasTrustDialogAccepted": True, "projectOnboardingSeenCount": 3}
        }
    }

    result = _run_prepare_claude_code_home(home, target_cwd, claude_json_contents=seed)
    assert result.returncode == 0, result.stderr

    managed_json = home / ".web-terminal-acp" / "claude-code-homes" / "window-trust" / ".claude.json"
    data = json.loads(managed_json.read_text(encoding="utf-8"))
    entry = data["projects"][target_real]
    assert entry["hasTrustDialogAccepted"] is True
    assert entry["projectOnboardingSeenCount"] == 3


def test_prepare_claude_code_home_skips_when_claude_json_missing(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()

    result = _run_prepare_claude_code_home(home, target_cwd, claude_json_contents=None)
    assert result.returncode == 0, result.stderr
