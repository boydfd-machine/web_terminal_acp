#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

NORMALIZED_VERSION = "0.0.0"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
PY_VERSION_RE = re.compile(r"(?m)^(__version__\s*=\s*[\"'])([^\"']+)([\"'])")
JSON_VERSION_RE = re.compile(r'(?m)^(\s*"version"\s*:\s*")([^"]+)(")')


class MergeError(Exception):
    pass


def _path_key(path: str) -> str:
    return path.replace("\\", "/")


def _field_count(path: str) -> int:
    path = _path_key(path)
    if path == "backend/app/version.py":
        return 1
    if path == "frontend/package.json":
        return 1
    if path == "frontend/package-lock.json":
        return 2
    raise MergeError(f"unsupported version file: {path}")


def _pattern(path: str) -> re.Pattern[str]:
    if _path_key(path) == "backend/app/version.py":
        return PY_VERSION_RE
    return JSON_VERSION_RE


def extract_versions(path: str, content: str) -> list[str]:
    count = _field_count(path)
    matches = list(_pattern(path).finditer(content))
    if len(matches) < count:
        raise MergeError(f"expected {count} version field(s) in {path}, found {len(matches)}")
    return [match.group(2) for match in matches[:count]]


def replace_versions(path: str, content: str, version: str) -> str:
    count = _field_count(path)
    replaced = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal replaced
        if replaced >= count:
            return match.group(0)
        replaced += 1
        return f"{match.group(1)}{version}{match.group(3)}"

    result = _pattern(path).sub(replacement, content)
    if replaced != count:
        raise MergeError(f"expected to replace {count} version field(s) in {path}, replaced {replaced}")
    return result


def _prerelease_key(prerelease: str | None) -> tuple[object, ...]:
    if prerelease is None:
        return (1,)
    parts: list[tuple[int, object]] = []
    for part in prerelease.split("."):
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part))
    return (0, *parts)


def semver_key(version: str) -> tuple[object, ...]:
    match = SEMVER_RE.match(version)
    if match is None:
        raise MergeError(f"not a SemVer version: {version}")
    major, minor, patch, prerelease = match.groups()
    return (int(major), int(minor), int(patch), *_prerelease_key(prerelease))


def highest_version(versions: list[str]) -> str:
    if not versions:
        raise MergeError("no versions found")
    return max(versions, key=semver_key)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def merge_normalized(path: str, base: str, current: str, other: str) -> tuple[str, int]:
    base_normalized = replace_versions(path, base, NORMALIZED_VERSION)
    current_normalized = replace_versions(path, current, NORMALIZED_VERSION)
    other_normalized = replace_versions(path, other, NORMALIZED_VERSION)

    with tempfile.TemporaryDirectory(prefix="web-terminal-version-merge-") as tmpdir:
        tmp = Path(tmpdir)
        base_path = tmp / "base"
        current_path = tmp / "current"
        other_path = tmp / "other"
        _write(base_path, base_normalized)
        _write(current_path, current_normalized)
        _write(other_path, other_normalized)
        result = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "-L",
                f"{path} (current)",
                "-L",
                f"{path} (base)",
                "-L",
                f"{path} (other)",
                str(current_path),
                str(base_path),
                str(other_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    if result.returncode not in (0, 1):
        message = result.stderr.strip() or f"git merge-file failed with exit {result.returncode}"
        raise MergeError(message)
    return result.stdout, result.returncode


def run(base_file: str, current_file: str, other_file: str, path: str) -> int:
    base = _read(base_file)
    current = _read(current_file)
    other = _read(other_file)
    selected_version = highest_version(
        extract_versions(path, base) + extract_versions(path, current) + extract_versions(path, other)
    )
    merged, merge_status = merge_normalized(path, base, current, other)
    merged = replace_versions(path, merged, selected_version)
    Path(current_file).write_text(merged, encoding="utf-8")
    if merge_status == 0:
        return 0
    print(
        f"web-terminal-version merge driver: resolved version to {selected_version}, "
        f"but {path} still has non-version conflicts",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: merge-version-conflict.py <base> <current> <other> <path>",
            file=sys.stderr,
        )
        return 2
    try:
        return run(argv[1], argv[2], argv[3], argv[4])
    except (OSError, MergeError) as exc:
        print(f"web-terminal-version merge driver: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
