from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path


class RequiredTestSuiteError(Exception):
    def __init__(self, suite: str, exit_code: int) -> None:
        super().__init__(f"{suite} full test suite failed with exit code {exit_code}")
        self.exit_code = exit_code


def required_test_suites(changed_files: Iterable[str]) -> tuple[str, ...]:
    paths = tuple(changed_files)
    suites: list[str] = []
    if any(_is_path_in_directory(path, "frontend") for path in paths):
        suites.append("frontend")
    if any(_is_path_in_directory(path, "backend") for path in paths):
        suites.append("backend")
    return tuple(suites)


def run_required_test_suites(repo_root: Path, changed_files: Iterable[str]) -> None:
    for suite in required_test_suites(changed_files):
        cwd, command = _test_suite_command(repo_root, suite)
        print(
            f"merge-agent-branch: running full {suite} tests: "
            f"cd {cwd.relative_to(repo_root)} && {' '.join(command)}",
            flush=True,
        )
        result = subprocess.run(command, cwd=cwd, check=False)
        if result.returncode != 0:
            raise RequiredTestSuiteError(suite, result.returncode)


def _test_suite_command(repo_root: Path, suite: str) -> tuple[Path, list[str]]:
    if suite == "frontend":
        return repo_root / "frontend", ["npm", "run", "test"]
    if suite == "backend":
        return repo_root / "backend", ["uv", "run", "pytest", "tests", "-n", "8", "-q"]
    raise ValueError(f"unknown required test suite: {suite}")


def _is_path_in_directory(path: str, directory: str) -> bool:
    return path == directory or path.startswith(f"{directory}/")
