from __future__ import annotations

import contextlib
import re
import shlex
from pathlib import Path
from uuid import UUID

from app.client_agent.shell_hook import build_managed_shell_command


class ManagedShellLauncherStore:
    def __init__(self, launcher_dir: Path, server_url: str) -> None:
        self.launcher_dir = launcher_dir
        self.server_url = server_url

    def command(
        self,
        *,
        client_id: UUID | str,
        window_id: UUID | str,
        shell: str,
        project_path: str | None = None,
        agent_ops_token: str | None = None,
    ) -> str:
        launcher_path = self.write(
            client_id=client_id,
            window_id=window_id,
            shell=shell,
            project_path=project_path,
            agent_ops_token=agent_ops_token,
        )
        return f"exec {shlex.quote(str(launcher_path))}"

    def write(
        self,
        *,
        client_id: UUID | str,
        window_id: UUID | str,
        shell: str,
        project_path: str | None = None,
        agent_ops_token: str | None = None,
    ) -> Path:
        self.launcher_dir.mkdir(parents=True, exist_ok=True)
        launcher_path = self.path(window_id)
        temp_path = launcher_path.with_name(f".{launcher_path.name}.tmp")
        managed_command = build_managed_shell_command(
            shell=shell,
            client_id=client_id,
            window_id=window_id,
            server_url=self.server_url,
            project_path=project_path,
            agent_ops_token=agent_ops_token,
        ).command
        temp_path.write_text(f"#!/bin/sh\n{managed_command}\n", encoding="utf-8")
        temp_path.chmod(0o700)
        temp_path.replace(launcher_path)
        return launcher_path

    def path(self, window_id: UUID | str) -> Path:
        safe_window_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(window_id)).strip("._")
        if not safe_window_id:
            safe_window_id = "window"
        return self.launcher_dir / f"{safe_window_id}.sh"

    def remove(self, window_id: UUID | str) -> None:
        with contextlib.suppress(OSError):
            self.path(window_id).unlink()
