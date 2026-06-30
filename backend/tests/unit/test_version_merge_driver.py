from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DRIVER_PATH = REPO_ROOT / "scripts" / "merge-version-conflict.py"

spec = importlib.util.spec_from_file_location("merge_version_conflict", DRIVER_PATH)
assert spec is not None
merge_version_conflict = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(merge_version_conflict)


def _run_merge(
    tmp_path: Path,
    *,
    path: str,
    base: str,
    current: str,
    other: str,
) -> tuple[int, str]:
    base_file = tmp_path / "base"
    current_file = tmp_path / "current"
    other_file = tmp_path / "other"
    base_file.write_text(base, encoding="utf-8")
    current_file.write_text(current, encoding="utf-8")
    other_file.write_text(other, encoding="utf-8")

    status = merge_version_conflict.run(
        str(base_file),
        str(current_file),
        str(other_file),
        path,
    )
    return status, current_file.read_text(encoding="utf-8")


def test_version_py_conflict_resolves_to_highest_semver(tmp_path: Path) -> None:
    base = '"""Shared application and client-agent version."""\n\n__version__ = "2.36.3"\n'
    current = '"""Shared application and client-agent version."""\n\n__version__ = "2.36.4"\n'
    other = '"""Shared application and client-agent version."""\n\n__version__ = "2.37.0"\n'

    status, merged = _run_merge(
        tmp_path,
        path="backend/app/version.py",
        base=base,
        current=current,
        other=other,
    )

    assert status == 0
    assert '__version__ = "2.37.0"' in merged
    assert "<<<<<<<" not in merged


def test_equal_versions_remain_unchanged(tmp_path: Path) -> None:
    content = '"""Shared application and client-agent version."""\n\n__version__ = "2.36.3"\n'

    status, merged = _run_merge(
        tmp_path,
        path="backend/app/version.py",
        base=content,
        current=content,
        other=content,
    )

    assert status == 0
    assert merged == content


def test_package_json_version_merge_preserves_non_version_changes(tmp_path: Path) -> None:
    base = """{
  "name": "web-terminal-acp-frontend",
  "private": true,
  "version": "2.36.3",
  "type": "module",
  "scripts": {
    "test": "vitest run"
  }
}
"""
    current = """{
  "name": "web-terminal-acp-frontend",
  "private": true,
  "description": "Local frontend",
  "version": "2.36.4",
  "type": "module",
  "scripts": {
    "test": "vitest run"
  }
}
"""
    other = """{
  "name": "web-terminal-acp-frontend",
  "private": true,
  "version": "2.37.0",
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "lint": "eslint ."
  }
}
"""

    status, merged = _run_merge(
        tmp_path,
        path="frontend/package.json",
        base=base,
        current=current,
        other=other,
    )

    assert status == 0
    assert '"version": "2.37.0"' in merged
    assert '"description": "Local frontend"' in merged
    assert '"lint": "eslint ."' in merged
    assert "<<<<<<<" not in merged


def test_package_lock_merge_updates_root_and_package_versions(tmp_path: Path) -> None:
    base = """{
  "name": "web-terminal-acp-frontend",
  "version": "2.36.3",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "name": "web-terminal-acp-frontend",
      "version": "2.36.3"
    }
  }
}
"""
    current = base.replace("2.36.3", "2.36.4")
    other = base.replace("2.36.3", "2.36.10")

    status, merged = _run_merge(
        tmp_path,
        path="frontend/package-lock.json",
        base=base,
        current=current,
        other=other,
    )

    assert status == 0
    assert merged.count('"version": "2.36.10"') == 2
    assert "<<<<<<<" not in merged


def test_non_version_conflict_is_left_for_manual_resolution(tmp_path: Path) -> None:
    base = """{
  "name": "web-terminal-acp-frontend",
  "private": true,
  "version": "2.36.3",
  "scripts": {
    "test": "base"
  }
}
"""
    current = base.replace('"version": "2.36.3"', '"version": "2.36.4"').replace(
        '"test": "base"',
        '"test": "ours"',
    )
    other = base.replace('"version": "2.36.3"', '"version": "2.37.0"').replace(
        '"test": "base"',
        '"test": "theirs"',
    )

    status, merged = _run_merge(
        tmp_path,
        path="frontend/package.json",
        base=base,
        current=current,
        other=other,
    )

    assert status == 1
    assert '"version": "2.37.0"' in merged
    assert "<<<<<<<" in merged
    assert '"test": "ours"' in merged
    assert '"test": "theirs"' in merged
