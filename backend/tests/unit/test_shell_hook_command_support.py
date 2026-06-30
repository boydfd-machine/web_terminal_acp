from __future__ import annotations

import os

import re

import subprocess

from uuid import UUID

from app.client_agent.shell_hook import (
    _agent_environment_script,
    _common_hook_script,
    build_managed_shell_command,
)

CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")

WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

SERVER_URL = "https://control.example.com"

def shell_loop_items(command: str, variable: str) -> set[str]:
    match = re.search(rf"for {re.escape(variable)} in ([^;]+); do", command)
    assert match is not None
    return set(match.group(1).split())

__all__ = [name for name in globals() if not name.startswith("__")]
