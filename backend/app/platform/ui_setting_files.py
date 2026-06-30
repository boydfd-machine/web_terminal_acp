from __future__ import annotations

import base64
import shutil
from pathlib import Path, PurePosixPath
from typing import Any


def file_tree_payload(root: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    if not root.is_dir():
        return {"version": 1, "files": files}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.is_symlink() or "__pycache__" in path.parts:
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "content_b64": base64.b64encode(path.read_bytes()).decode("ascii"),
                "mode": path.stat().st_mode & 0o777,
            }
        )
    return {"version": 1, "files": files}


def restore_file_tree_payload(root: Path, payload: object) -> None:
    files = _file_records(payload)
    if root.is_dir() and not root.is_symlink():
        shutil.rmtree(root)
    else:
        root.unlink(missing_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content, mode in files:
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if mode is not None:
            target.chmod(mode)


def _file_records(payload: object) -> list[tuple[str, bytes, int | None]]:
    if not isinstance(payload, dict):
        return []
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        return []
    files: list[tuple[str, bytes, int | None]] = []
    for item in raw_files:
        record = _file_record(item)
        if record is not None:
            files.append(record)
    return files


def _file_record(item: object) -> tuple[str, bytes, int | None] | None:
    if not isinstance(item, dict):
        return None
    relative_path = item.get("path")
    content_b64 = item.get("content_b64")
    if not isinstance(relative_path, str) or not isinstance(content_b64, str):
        return None
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    try:
        content = base64.b64decode(content_b64.encode("ascii"), validate=True)
    except ValueError:
        return None
    mode = _file_mode(item.get("mode"))
    return path.as_posix(), content, mode


def _file_mode(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 0o777:
        return value
    return None
