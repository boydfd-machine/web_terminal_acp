from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "merge-agent-branch.py"

spec = importlib.util.spec_from_file_location("merge_agent_branch", SCRIPT_PATH)
assert spec is not None
merge_agent_branch = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(merge_agent_branch)

validation_spec = importlib.util.spec_from_file_location(
    "merge_agent_validation",
    REPO_ROOT / "scripts" / "merge_agent_validation.py",
)
assert validation_spec is not None
merge_agent_validation = importlib.util.module_from_spec(validation_spec)
assert validation_spec.loader is not None
validation_spec.loader.exec_module(merge_agent_validation)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_unchecked(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "test@example.com")
    _git(main, "config", "user.name", "Test User")
    (main / "file.txt").write_text("base\n", encoding="utf-8")
    _commit(main, "base")
    agent = tmp_path / "agent"
    _git(main, "worktree", "add", "-b", "agent/feature", str(agent))
    return main, agent


def _init_managed_repo(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "test@example.com")
    _git(main, "config", "user.name", "Test User")
    (main / ".gitignore").write_text(".web-terminal-acp/\n", encoding="utf-8")
    (main / "file.txt").write_text("base\n", encoding="utf-8")
    _commit(main, "base")
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    agent.parent.mkdir(parents=True)
    _git(main, "worktree", "add", "-b", "agent/feature", str(agent))
    return main, agent


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        _git_unchecked(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode
        == 0
    )


def _worktree_list(repo: Path) -> str:
    return _git(repo, "worktree", "list", "--porcelain").stdout


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
