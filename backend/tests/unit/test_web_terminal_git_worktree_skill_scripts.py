from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "backend" / "app" / "resources" / "system_skills" / "web-terminal-git-worktree"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_script(
    script: Path,
    cwd: Path,
    *,
    window_id: str = "window-1",
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WEB_TERMINAL_WINDOW_ID"] = window_id
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_skill_dir_command(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WEB_TERMINAL_WINDOW_ID"] = "window-1"
    env["SKILL_DIR"] = str(SKILL_ROOT)
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _init_repo(tmp_path: Path) -> Path:
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "test@example.com")
    _git(main, "config", "user.name", "Test User")
    (main / "file.txt").write_text("base\n", encoding="utf-8")
    _git(main, "add", "file.txt")
    _git(main, "commit", "-m", "base")
    return main


def _write_dependency_dirs(main: Path) -> None:
    backend_bin = main / "backend" / ".venv" / "bin"
    backend_bin.mkdir(parents=True)
    (backend_bin / "pytest").write_text("#!/usr/bin/env python\n", encoding="utf-8")
    frontend_pkg = main / "frontend" / "node_modules" / "demo-pkg"
    frontend_pkg.mkdir(parents=True)
    (frontend_pkg / "index.js").write_text("export default 1;\n", encoding="utf-8")


def _add_agent_worktree(main: Path, window_id: str = "window-1") -> Path:
    agent = main / ".web-terminal-acp" / "worktrees" / window_id
    agent.parent.mkdir(parents=True)
    _git(main, "worktree", "add", "-b", "agent/feature", str(agent))
    return agent


def test_skill_doc_uses_skill_relative_commands_and_migration_gate() -> None:
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for script_name in ("setup-git-worktree.sh", "register-worktree.sh", "remove-worktree.sh"):
        assert f'bash "$SKILL_DIR/scripts/{script_name}"' in skill_md
    assert "init-worktree.sh" in skill_md
    assert ".cursor/skills/web-terminal-git-worktree" not in skill_md
    assert ".codex/skills/web-terminal-git-worktree" not in skill_md
    assert ".claude/skills/web-terminal-git-worktree" not in skill_md
    assert "--frontend" in skill_md
    assert "--backend" in skill_md
    assert "cp -a" in skill_md
    assert "Migration Conflict Gate" in skill_md
    assert "git merge main" in skill_md
    assert 'python3 "$SKILL_DIR/scripts/merge-agent-branch.py"' in skill_md
    assert "Full tests before merge" in skill_md
    assert "cd frontend && npm run test" in skill_md
    assert "cd backend && uv run pytest tests -n 8 -q" in skill_md
    assert 'DATABASE_URL="sqlite+aiosqlite:///$tmp_db" uv run alembic upgrade head' in skill_md
    assert "merge `main` again and repeat the migration conflict gate" in skill_md


def test_init_script_wraps_setup_script() -> None:
    init_script = (SKILL_ROOT / "scripts" / "init-worktree.sh").read_text(encoding="utf-8")

    assert 'exec bash "$SCRIPT_DIR/setup-git-worktree.sh"' in init_script
    assert 'exec "$SCRIPT_DIR/setup-git-worktree.sh"' not in init_script


def test_setup_worktree_copies_backend_and_frontend_dependencies_by_default(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    _write_dependency_dirs(main)

    result = _run_script(
        SKILL_ROOT / "scripts" / "setup-git-worktree.sh",
        main,
        args=("setup-defaults",),
    )

    assert result.returncode == 0, result.stderr
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    assert _git(agent, "branch", "--show-current").stdout.strip() == "agent/setup-defaults"
    backend_source = main / "backend" / ".venv" / "bin" / "pytest"
    backend_target = agent / "backend" / ".venv" / "bin" / "pytest"
    frontend_source = main / "frontend" / "node_modules" / "demo-pkg" / "index.js"
    frontend_target = agent / "frontend" / "node_modules" / "demo-pkg" / "index.js"
    assert backend_target.read_text(encoding="utf-8") == backend_source.read_text(encoding="utf-8")
    assert frontend_target.read_text(encoding="utf-8") == frontend_source.read_text(encoding="utf-8")
    assert not (agent / "backend" / ".venv").is_symlink()
    assert not (agent / "frontend" / "node_modules").is_symlink()
    assert backend_target.stat().st_ino != backend_source.stat().st_ino
    assert frontend_target.stat().st_ino != frontend_source.stat().st_ino
    assert "copying backend .venv from main checkout" in result.stdout
    assert "copying frontend node_modules from main checkout" in result.stdout


def test_setup_worktree_frontend_only_skips_backend_dependencies(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    _write_dependency_dirs(main)

    result = _run_script(
        SKILL_ROOT / "scripts" / "setup-git-worktree.sh",
        main,
        args=("--frontend", "frontend-only"),
    )

    assert result.returncode == 0, result.stderr
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    assert (agent / "frontend" / "node_modules" / "demo-pkg" / "index.js").is_file()
    assert not (agent / "backend" / ".venv").exists()


def test_setup_worktree_backend_only_skips_frontend_dependencies(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    _write_dependency_dirs(main)

    result = _run_script(
        SKILL_ROOT / "scripts" / "setup-git-worktree.sh",
        main,
        args=("--backend", "backend-only"),
    )

    assert result.returncode == 0, result.stderr
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    assert (agent / "backend" / ".venv" / "bin" / "pytest").is_file()
    assert not (agent / "frontend" / "node_modules").exists()


def test_init_worktree_from_main_repo_subdirectory(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    subdir = main / "backend"
    subdir.mkdir()

    result = _run_script(
        SKILL_ROOT / "scripts" / "init-worktree.sh",
        subdir,
        args=("feature-from-subdir",),
    )

    assert result.returncode == 0, result.stderr
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    assert agent.is_dir()
    assert (agent / ".git").is_file()
    assert _git(agent, "branch", "--show-current").stdout.strip() == "agent/feature-from-subdir"
    assert "Registered worktree:" in result.stdout


def test_skill_dir_script_command_from_main_repo_subdirectory(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    subdir = main / "backend"
    subdir.mkdir()

    result = _run_skill_dir_command(
        'bash "$SKILL_DIR/scripts/init-worktree.sh" feature-from-doc-command',
        subdir,
    )

    assert result.returncode == 0, result.stderr
    agent = main / ".web-terminal-acp" / "worktrees" / "window-1"
    assert agent.is_dir()
    assert _git(agent, "branch", "--show-current").stdout.strip() == "agent/feature-from-doc-command"


def test_skill_dir_script_commands_from_linked_worktree_subdirectory(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    agent = _add_agent_worktree(main)
    subdir = agent / "backend"
    subdir.mkdir()

    register = _run_skill_dir_command('bash "$SKILL_DIR/scripts/register-worktree.sh"', subdir)
    remove = _run_skill_dir_command('bash "$SKILL_DIR/scripts/remove-worktree.sh"', subdir)

    assert register.returncode == 0, register.stderr
    assert "web-terminal-worktree" in register.stdout
    assert f"Registered worktree: {agent}" in register.stdout
    assert remove.returncode == 0, remove.stderr
    assert not agent.exists()
    assert "Removed worktree: .web-terminal-acp/worktrees/window-1" in remove.stdout


def test_skill_dir_merge_agent_command_lands_and_cleans_worktree(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    agent = _add_agent_worktree(main)
    (agent / "file.txt").write_text("base\nagent\n", encoding="utf-8")
    _git(agent, "add", "file.txt")
    _git(agent, "commit", "-m", "agent change")

    result = _run_skill_dir_command(
        'python3 "$SKILL_DIR/scripts/merge-agent-branch.py"',
        agent,
    )

    assert result.returncode == 0, result.stderr
    assert "fast-forwarding main to agent/feature" in result.stdout
    assert not agent.exists()
    assert "agent/feature" not in _git(main, "branch", "--list", "agent/feature").stdout
    assert (main / "file.txt").read_text(encoding="utf-8") == "base\nagent\n"


def test_merge_agent_script_has_validation_helper() -> None:
    assert (SKILL_ROOT / "scripts" / "merge_agent_validation.py").is_file()
    script = (SKILL_ROOT / "scripts" / "merge-agent-branch.py").read_text(encoding="utf-8")
    assert "from merge_agent_validation import" in script
    assert "run_required_test_suites" in script


def test_register_worktree_from_linked_worktree_subdirectory(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    agent = _add_agent_worktree(main)
    subdir = agent / "backend"
    subdir.mkdir()

    result = _run_script(SKILL_ROOT / "scripts" / "register-worktree.sh", subdir)

    assert result.returncode == 0, result.stderr
    assert "web-terminal-worktree" in result.stdout
    assert f"Registered worktree: {agent}" in result.stdout


def test_remove_worktree_from_linked_worktree_subdirectory(tmp_path: Path) -> None:
    main = _init_repo(tmp_path)
    agent = _add_agent_worktree(main)
    subdir = agent / "backend"
    subdir.mkdir()

    result = _run_script(SKILL_ROOT / "scripts" / "remove-worktree.sh", subdir)

    assert result.returncode == 0, result.stderr
    assert not agent.exists()
    assert "agent/feature" not in _git(main, "branch", "--list", "agent/feature").stdout
    assert "Removed worktree: .web-terminal-acp/worktrees/window-1" in result.stdout
