from __future__ import annotations

import shutil
import subprocess

from app.contexts.agent_profiles.domain.cursor_official_models import parse_cursor_official_models_output


def list_cursor_official_models() -> list[dict[str, str]]:
    for command in _cursor_official_model_commands():
        completed = _run_cursor_official_models_command(command)
        if completed is None:
            continue
        models = parse_cursor_official_models_output(completed.stdout)
        if models:
            return models
    return []


def _cursor_official_model_commands() -> tuple[list[str], ...]:
    command = shutil.which("cursor-agent") or shutil.which("agent")
    if command is None:
        return ()
    commands: list[list[str]] = []
    proxychains = shutil.which("proxychains4") or shutil.which("proxychains")
    if proxychains is not None:
        commands.append([proxychains, "-q", command, "models"])
    commands.append([command, "models"])
    return tuple(commands)


def _run_cursor_official_models_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed
