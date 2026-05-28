from __future__ import annotations

from pathlib import Path
import re


def test_backend_claude_mount_uses_host_prefixed_env_var() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert re.search(r"\$\{HOST_CLAUDE_CONFIG_DIR:-[^}]+\}:/home/appuser/\.claude\b", content)
    assert re.search(r"\$\{HOST_CLAUDE_JSON:-[^}]+\}:/home/appuser/\.claude\.json\b", content)
    assert not re.search(r"\$\{CLAUDE_CONFIG_DIR:-[^}]+\}:/home/appuser/\.claude\b", content)
