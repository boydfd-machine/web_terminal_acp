# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

import tomllib


def _run_prepare_codex_home(home, cwd, *, config_text=None, project_path=None):
    if config_text is not None:
        source_home = home / ".codex"
        source_home.mkdir(parents=True, exist_ok=True)
        (source_home / "config.toml").write_text(config_text, encoding="utf-8")
    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-trust",
        "WEB_TERMINAL_ORIGINAL_CODEX_HOME": "~/.codex",
        "WEB_TERMINAL_PROJECT_PATH": project_path or "",
        "CODEX_HOME": "",
    }
    return subprocess.run(
        ["bash", "-c", f"{_agent_environment_script()}\n__web_terminal_prepare_codex_home\n"],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
    )


def test_prepare_codex_home_marks_cwd_as_trusted_without_touching_global_config(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    original_config = 'model = "gpt-5.5"\n'

    result = _run_prepare_codex_home(home, target_cwd, config_text=original_config)
    assert result.returncode == 0, result.stderr

    managed_config = home / ".web-terminal-acp" / "codex-homes" / "window-trust" / "config.toml"
    assert managed_config.exists()
    assert not managed_config.is_symlink()
    assert (home / ".codex" / "config.toml").read_text(encoding="utf-8") == original_config

    data = tomllib.loads(managed_config.read_text(encoding="utf-8"))
    assert data["model"] == "gpt-5.5"
    assert data["projects"][str(target_cwd.resolve())]["trust_level"] == "trusted"


def test_prepare_codex_home_updates_existing_project_trust_entry(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()
    target_real = str(target_cwd.resolve())
    managed_home = home / ".web-terminal-acp" / "codex-homes" / "window-trust"
    managed_home.mkdir(parents=True)
    managed_config = managed_home / "config.toml"
    managed_config.write_text(
        f'[projects."{target_real}"]\ntrust_level = "untrusted"\n',
        encoding="utf-8",
    )

    result = _run_prepare_codex_home(home, target_cwd)
    assert result.returncode == 0, result.stderr

    text = managed_config.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["projects"][target_real]["trust_level"] == "trusted"
    assert text.count("trust_level") == 1


def test_prepare_codex_home_marks_project_path_when_shell_cwd_differs(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    shell_cwd = tmp_path / "shell"
    shell_cwd.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()

    result = _run_prepare_codex_home(home, shell_cwd, project_path=str(project_path))
    assert result.returncode == 0, result.stderr

    managed_config = home / ".web-terminal-acp" / "codex-homes" / "window-trust" / "config.toml"
    data = tomllib.loads(managed_config.read_text(encoding="utf-8"))
    projects = data["projects"]
    assert projects[str(shell_cwd.resolve())]["trust_level"] == "trusted"
    assert projects[str(project_path.resolve())]["trust_level"] == "trusted"
