from __future__ import annotations

import contextlib
import os
from collections.abc import Iterable


def mountinfo_bind_path_pairs(lines: Iterable[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in lines:
        parts = line.rstrip("\n").split(" ")
        if " - " not in line:
            continue
        separator_index = parts.index("-")
        if separator_index < 5:
            continue
        root = parts[3].replace("\\040", " ").rstrip("/")
        mount_point = parts[4].replace("\\040", " ")
        if root.startswith("/") and root != "/" and mount_point.startswith("/"):
            pairs.append((root, mount_point.rstrip("/")))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


def docker_bind_mount_path_pairs() -> list[tuple[str, str]]:
    if not os.path.exists("/.dockerenv"):
        return []
    with contextlib.suppress(OSError):
        with open("/proc/self/mountinfo", encoding="utf-8") as mountinfo:
            return mountinfo_bind_path_pairs(mountinfo)
    return []


def map_host_path_to_container_path(
    path: str,
    bind_mounts: list[tuple[str, str]] | None = None,
) -> str:
    for source, mount_point in bind_mounts if bind_mounts is not None else docker_bind_mount_path_pairs():
        if path == source:
            return mount_point or "/"
        if path.startswith(f"{source}/"):
            suffix = path[len(source) :].lstrip("/")
            return os.path.join(mount_point or "/", suffix)
    return path
