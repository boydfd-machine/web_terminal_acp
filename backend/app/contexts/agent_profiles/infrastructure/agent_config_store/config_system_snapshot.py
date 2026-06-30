from __future__ import annotations

import base64
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .config_model_types import SYSTEM_MODEL_PRESETS_FILE
from .config_system import (
    SYSTEM_DEFAULTS_FILE,
    SYSTEM_DISABLED_SKILLS_DIR,
    SYSTEM_MCP_DISABLED_FILE,
    SYSTEM_MCP_FILE,
    SYSTEM_SKILLS_DIR,
    _system_config_root,
)


def system_agent_config_files_payload(*, home: Path | None = None) -> dict[str, object]:
    root = _system_config_root(home or Path.home())
    files: list[dict[str, object]] = []
    if not root.is_dir():
        return {"version": 1, "files": files}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.is_symlink():
            continue
        relative_path = path.relative_to(root).as_posix()
        if relative_path == SYSTEM_MODEL_PRESETS_FILE:
            continue
        try:
            content = path.read_bytes()
            mode = path.stat().st_mode & 0o777
        except FileNotFoundError:
            continue
        files.append(
            {
                "path": relative_path,
                "content_b64": base64.b64encode(content).decode("ascii"),
                "mode": mode,
            }
        )
    return {"version": 1, "files": files}


def restore_system_agent_config_files_payload(
    payload: object,
    *,
    home: Path | None = None,
) -> None:
    root = _system_config_root(home or Path.home())
    root.mkdir(parents=True, exist_ok=True)
    for path in _managed_system_config_paths(root):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    for relative_path, content, mode in _system_agent_config_file_records(payload):
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if mode is not None:
            target.chmod(mode)


def _managed_system_config_paths(root: Path) -> tuple[Path, ...]:
    return (
        root / SYSTEM_SKILLS_DIR,
        root / SYSTEM_DISABLED_SKILLS_DIR,
        root / SYSTEM_MCP_FILE,
        root / SYSTEM_MCP_DISABLED_FILE,
        root / SYSTEM_DEFAULTS_FILE,
    )


def _system_agent_config_file_records(
    payload: object,
) -> list[tuple[str, bytes, int | None]]:
    if not isinstance(payload, dict):
        return []
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        return []
    files: list[tuple[str, bytes, int | None]] = []
    for item in raw_files:
        record = _system_agent_config_file_record(item)
        if record is not None:
            files.append(record)
    return files


def _system_agent_config_file_record(
    item: object,
) -> tuple[str, bytes, int | None] | None:
    if not isinstance(item, dict):
        return None
    relative_path = item.get("path")
    content_b64 = item.get("content_b64")
    if not isinstance(relative_path, str) or not isinstance(content_b64, str):
        return None
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if relative_path == SYSTEM_MODEL_PRESETS_FILE:
        return None
    try:
        content = base64.b64decode(content_b64.encode("ascii"), validate=True)
    except ValueError:
        return None
    return path.as_posix(), content, _file_mode(item.get("mode"))


def _file_mode(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 0o777:
        return value
    return None
