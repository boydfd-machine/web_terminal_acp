# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

import pytest


def _base_agent_env(home, bin_dir):
    return {
        "HOME": str(home),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-1",
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-1",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_HOME": "~/.web-terminal-acp/antigravity-cli-homes/window-1",
        "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME": "~/.web-terminal-acp/antigravity-cli-homes/.managed-home/window-1",
        "WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME": "~/.gemini/antigravity-cli",
        "WEB_TERMINAL_ORIGINAL_HOME": "~",
        "CODEX_HOME": "",
    }


def _write_agent_executable(bin_dir, name):
    path = bin_dir / name
    path.write_text(
        "#!/bin/sh\n"
        f"printf 'ran:{name}:%s:%s:%s:%s\\n' "
        '"${CODEX_HOME:-}" "${CLAUDE_CONFIG_DIR:-}" "${CURSOR_AGENT_HOME:-}" "$HOME"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _managed_roots(home):
    web_terminal = home / ".web-terminal-acp"
    return {
        "codex": web_terminal / "codex-homes" / "window-1",
        "claude": web_terminal / "claude-code-homes" / "window-1",
        "cursor": web_terminal / "cursor-homes" / "window-1",
        "antigravity": web_terminal / "antigravity-cli-homes" / "window-1",
    }


def _run_agent_environment_script(script, env):
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )


def test_agent_environment_script_does_not_materialize_agent_homes_until_command_runs(
    tmp_path,
) -> None:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    home.mkdir()
    bin_dir.mkdir()

    result = _run_agent_environment_script(
        _agent_environment_script(),
        _base_agent_env(home, bin_dir),
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert all(not path.exists() for path in _managed_roots(home).values())


@pytest.mark.parametrize(
    ("command", "created_key"),
    [
        ("codex --version", "codex"),
        ("claude --version", "claude"),
        ("agent --version", "cursor"),
    ],
)
def test_agent_command_wrapper_materializes_only_the_requested_agent_home(
    tmp_path,
    command,
    created_key,
) -> None:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    home.mkdir()
    bin_dir.mkdir()
    for executable in ("codex", "claude", "agent"):
        _write_agent_executable(bin_dir, executable)

    result = _run_agent_environment_script(
        f"{_agent_environment_script()}\n"
        "__web_terminal_install_agent_permission_wrappers\n"
        f"{command}\n",
        _base_agent_env(home, bin_dir),
    )

    roots = _managed_roots(home)
    assert result.returncode == 0, result.stderr
    assert f"ran:{command.split()[0]}:" in result.stdout
    assert roots[created_key].exists()
    assert all(not path.exists() for key, path in roots.items() if key != created_key)


def test_antigravity_command_wrapper_materializes_only_antigravity_home(tmp_path) -> None:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    home.mkdir()
    bin_dir.mkdir()
    _write_agent_executable(bin_dir, "agy-p")

    result = _run_agent_environment_script(
        f"{_agent_environment_script()}\n"
        "__web_terminal_install_agent_permission_wrappers\n"
        "__web_terminal_run_agent_command agy-p --version\n",
        _base_agent_env(home, bin_dir),
    )

    roots = _managed_roots(home)
    assert result.returncode == 0, result.stderr
    assert "ran:agy-p:" in result.stdout
    assert roots["antigravity"].exists()
    assert all(not path.exists() for key, path in roots.items() if key != "antigravity")


def test_existing_agent_home_does_not_reinitialize_global_config_links(tmp_path) -> None:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    source_codex = home / ".codex"
    managed_codex = home / ".web-terminal-acp" / "codex-homes" / "window-1"
    home.mkdir()
    bin_dir.mkdir()
    source_codex.mkdir()
    managed_codex.mkdir(parents=True)
    (source_codex / "auth.json").write_text("{}", encoding="utf-8")
    _write_agent_executable(bin_dir, "codex")

    result = _run_agent_environment_script(
        f"{_agent_environment_script()}\n"
        "__web_terminal_install_agent_permission_wrappers\n"
        "codex --version\n",
        _base_agent_env(home, bin_dir),
    )

    assert result.returncode == 0, result.stderr
    assert "ran:codex:" in result.stdout
    assert not (managed_codex / "auth.json").exists()
