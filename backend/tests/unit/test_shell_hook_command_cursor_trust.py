# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

import json
import subprocess

from app.contexts.agent_profiles.domain.cursor_official_models import cursor_project_dir_name


def _run_prepare_cursor_home(home, cwd, *, project_path=None):
    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-trust",
        "WEB_TERMINAL_ORIGINAL_CURSOR_DIR": "~/.cursor",
        "WEB_TERMINAL_PROJECT_PATH": project_path or "",
    }
    return subprocess.run(
        ["bash", "-c", f"{_agent_environment_script()}\n__web_terminal_prepare_cursor_home\n"],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
    )


def test_prepare_cursor_home_marks_cwd_as_trusted_in_managed_projects(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target_cwd = tmp_path / "project"
    target_cwd.mkdir()

    result = _run_prepare_cursor_home(home, target_cwd)
    assert result.returncode == 0, result.stderr

    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-trust"
    trust_path = (
        managed_cursor
        / "projects"
        / cursor_project_dir_name(str(target_cwd))
        / ".workspace-trusted"
    )
    assert trust_path.is_file()
    payload = json.loads(trust_path.read_text(encoding="utf-8"))
    assert payload["workspacePath"] == str(target_cwd.resolve())
    assert payload["trustedAt"].endswith("Z")


def test_prepare_cursor_home_marks_project_path_as_trusted(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    shell_cwd = tmp_path / "shell"
    shell_cwd.mkdir()
    project_path = tmp_path / "repo"
    project_path.mkdir()

    result = _run_prepare_cursor_home(home, shell_cwd, project_path=str(project_path))
    assert result.returncode == 0, result.stderr

    managed_cursor = home / ".web-terminal-acp" / "cursor-homes" / "window-trust"
    for path in (shell_cwd, project_path):
        assert (
            managed_cursor
            / "projects"
            / cursor_project_dir_name(str(path))
            / ".workspace-trusted"
        ).is_file()
