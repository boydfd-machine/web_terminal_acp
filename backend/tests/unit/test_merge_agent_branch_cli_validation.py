from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.merge_agent_branch_test_support import (
    _commit,
    _git,
    _init_repo,
    merge_agent_branch,
    merge_agent_validation,
)


def test_required_test_suites_follow_changed_top_level_paths() -> None:
    assert merge_agent_validation.required_test_suites(
        [
            "frontend/src/App.tsx",
            "frontend/tests/app.test.tsx",
            "backend/app/version.py",
            "docs/note.md",
        ]
    ) == ("frontend", "backend")
    assert merge_agent_validation.required_test_suites(["scripts/merge-agent-branch.py"]) == ()


def test_required_test_suites_use_full_frontend_and_backend_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "frontend").mkdir()
    (repo / "backend").mkdir()
    run_calls: list[tuple[Path, list[str]]] = []

    def fake_run(command, cwd=None, check=False, **_kwargs):
        run_calls.append((Path(cwd), list(command)))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(merge_agent_validation.subprocess, "run", fake_run)

    merge_agent_validation.run_required_test_suites(
        repo,
        ["frontend/src/App.tsx", "backend/app/version.py"],
    )

    assert run_calls == [
        (repo / "frontend", ["npm", "run", "test"]),
        (repo / "backend", ["uv", "run", "pytest", "tests", "-n", "8", "-q"]),
    ]


def test_landing_runs_required_test_gate_for_frontend_and_backend_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "frontend" / "src").mkdir(parents=True)
    (agent / "frontend" / "src" / "App.tsx").write_text("export {}\n", encoding="utf-8")
    (agent / "backend" / "app").mkdir(parents=True)
    (agent / "backend" / "app" / "version.py").write_text('__version__ = "0.0.1"\n', encoding="utf-8")
    _commit(agent, "full test gated changes")
    validation_calls: list[tuple[Path, list[str]]] = []

    def fake_validation(repo_root: Path, changed_files: list[str]) -> None:
        validation_calls.append((repo_root, sorted(changed_files)))

    monkeypatch.setattr(merge_agent_branch, "run_required_test_suites", fake_validation)

    status = merge_agent_branch.merge_agent_branch(
        branch="agent/feature",
        worktree=agent,
        main_worktree=main,
    )

    assert status == 0
    assert validation_calls == [
        (agent, ["backend/app/version.py", "frontend/src/App.tsx"]),
    ]


def test_required_full_test_failure_blocks_main_fast_forward(
    tmp_path: Path,
    monkeypatch,
) -> None:
    main, agent = _init_repo(tmp_path)
    (agent / "frontend").mkdir()
    (agent / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    _commit(agent, "frontend change")
    main_head = _git(main, "rev-parse", "--short", "HEAD").stdout.strip()

    def fake_validation(repo_root: Path, changed_files: list[str]) -> None:
        raise merge_agent_branch.RequiredTestSuiteError("frontend", 7)

    monkeypatch.setattr(merge_agent_branch, "run_required_test_suites", fake_validation)

    try:
        merge_agent_branch.merge_agent_branch(
            branch="agent/feature",
            worktree=agent,
            main_worktree=main,
        )
    except merge_agent_branch.MergeAgentError as exc:
        assert exc.exit_code == 7
        assert "frontend full test suite failed" in str(exc)
    else:
        raise AssertionError("expected failing frontend suite to block landing")

    assert _git(main, "rev-parse", "--short", "HEAD").stdout.strip() == main_head
