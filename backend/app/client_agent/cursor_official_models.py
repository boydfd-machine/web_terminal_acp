from __future__ import annotations

import shutil
import subprocess

from app.contexts.agent_profiles.domain.cursor_official_models import parse_cursor_official_models_output


def list_cursor_official_models() -> list[dict[str, str]]:
    command = shutil.which("agent") or shutil.which("cursor-agent")
    if command is None:
        return []
    try:
        completed = subprocess.run(
            [command, "models"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return parse_cursor_official_models_output(completed.stdout)
