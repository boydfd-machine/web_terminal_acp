# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

import os
import subprocess


def _write_skill(path, skill_id: str) -> None:
    target = path / skill_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(f"---\nname: {skill_id}\n---\n", encoding="utf-8")


def test_prepare_cursor_skill_home_points_cursor_at_managed_skills(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    global_cursor = home / ".cursor" / "skills-cursor"
    global_claude = home / ".claude" / "skills"
    _write_skill(global_cursor, "global-builtin")
    _write_skill(global_claude, "global-claude")

    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    _write_skill(managed_cursor / "skills-cursor", "managed-skill")

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f"{_agent_environment_script()}\n"
                "__web_terminal_prepare_cursor_home\n"
                "printf 'overlay=%s\\n' \"$WEB_TERMINAL_CURSOR_SKILL_HOME\"\n"
                "ls \"$WEB_TERMINAL_CURSOR_SKILL_HOME/.cursor/skills-cursor\"\n"
                "ls \"$WEB_TERMINAL_CURSOR_SKILL_HOME/.claude/skills\"\n"
            ),
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    overlay = managed_cursor / "skill-home"
    assert f"overlay={overlay}" in result.stdout
    assert "managed-skill" in result.stdout
    assert "global-builtin" not in result.stdout
    assert "global-claude" not in result.stdout
    assert (overlay / ".cursor" / "skills-cursor").resolve() == managed_cursor / "skills-cursor"


def test_run_cursor_agent_command_uses_skill_home_overlay(tmp_path) -> None:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    home.mkdir()
    bin_dir.mkdir()
    _write_skill(home / ".cursor" / "skills-cursor", "global-builtin")
    _write_skill(home / ".claude" / "skills", "global-claude")
    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    _write_skill(managed_cursor / "skills-cursor", "managed-skill")

    agent_stub = bin_dir / "agent"
    agent_stub.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'home=%s\\n' \"$HOME\"\n"
        "ls \"$HOME/.cursor/skills-cursor\"\n"
        "ls \"$HOME/.claude/skills\"\n",
        encoding="utf-8",
    )
    agent_stub.chmod(0o755)

    env = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"{_agent_environment_script()}\n__web_terminal_run_cursor_agent_command agent\n",
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    overlay = managed_cursor / "skill-home"
    assert f"home={overlay}" in result.stdout
    assert "managed-skill" in result.stdout
    assert "global-builtin" not in result.stdout
    assert "global-claude" not in result.stdout


def test_prepare_cursor_skill_home_links_cursor_state_back_to_managed_home(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    source_auth = home / ".config" / "cursor" / "auth.json"
    source_auth.parent.mkdir(parents=True)
    source_auth.write_text('{"loggedIn":true}\n', encoding="utf-8")
    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    managed_cursor.mkdir(parents=True)

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f"{_agent_environment_script()}\n"
                "__web_terminal_prepare_cursor_home\n"
                "printf 'config=%s\\n' \"$WEB_TERMINAL_CURSOR_SKILL_HOME/.cursor/cli-config.json\"\n"
                "printf 'state=%s\\n' \"$WEB_TERMINAL_CURSOR_SKILL_HOME/.cursor/agent-cli-state.json\"\n"
            ),
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    overlay = managed_cursor / "skill-home"
    assert (overlay / ".cursor" / "cli-config.json").resolve() == managed_cursor / "cli-config.json"
    assert (overlay / ".cursor" / "agent-cli-state.json").resolve() == managed_cursor / "agent-cli-state.json"
    assert (overlay / ".config" / "cursor" / "auth.json").resolve() == source_auth


def test_prepare_cursor_skill_home_links_project_trust_back_to_managed_home(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-1"
    managed_cursor.mkdir(parents=True)

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f"{_agent_environment_script()}\n"
                "__web_terminal_prepare_cursor_home\n"
                "printf 'projects=%s\\n' \"$WEB_TERMINAL_CURSOR_SKILL_HOME/.cursor/projects\"\n"
            ),
        ],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=str(target_cwd),
    )

    assert result.returncode == 0, result.stderr
    overlay = managed_cursor / "skill-home"
    project_dir = target_cwd.resolve().as_posix().lstrip("/").replace("/", "-")
    assert (overlay / ".cursor" / "projects").resolve() == managed_cursor / "projects"
    assert (overlay / ".cursor" / "projects" / project_dir / ".workspace-trusted").is_file()
