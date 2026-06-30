from __future__ import annotations

import contextlib
from pathlib import Path


def shared_cache_root(home: Path) -> Path:
    return home / ".web-terminal-acp" / "shared-cache"


def codex_shared_tmp_root(home: Path) -> Path:
    return shared_cache_root(home) / "codex" / "tmp"


def link_shared_agent_cache_items(agent: str, managed_root: Path, *, home: Path) -> None:
    if agent != "codex":
        return
    _link_absent_directory(managed_root / ".tmp", codex_shared_tmp_root(home))


def _link_absent_directory(target: Path, source: Path) -> None:
    if target.exists() or target.is_symlink():
        return
    source.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        target.symlink_to(source, target_is_directory=True)
