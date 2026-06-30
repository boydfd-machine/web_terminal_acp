from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2].parent


def test_open_source_sync_excludes_internal_release_material(tmp_path: Path) -> None:
    target = tmp_path / "web_terminal_acp_github"
    script = REPO_ROOT / "scripts" / "sync-to-github.sh"
    local_only_markers = [
        REPO_ROOT / "docs" / "analysis" / "open-source-sync-test-marker.md",
        REPO_ROOT / "docs" / "blog" / "open-source-sync-test-marker.md",
        REPO_ROOT / "dogfood-output" / "open-source-sync-test-marker.txt",
    ]
    for marker in local_only_markers:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("local-only release material\n", encoding="utf-8")

    try:
        result = subprocess.run(
            ["bash", str(script), "test open source sync"],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "GITHUB_REPO_DIR": str(target),
                "GIT_AUTHOR_NAME": "Web Terminal Test",
                "GIT_AUTHOR_EMAIL": "web-terminal-test@example.com",
                "GIT_COMMITTER_NAME": "Web Terminal Test",
                "GIT_COMMITTER_EMAIL": "web-terminal-test@example.com",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        for marker in local_only_markers:
            marker.unlink(missing_ok=True)

    assert result.returncode == 0, result.stdout + result.stderr

    assert (target / "README.md").is_file()
    assert (target / "docker-compose.yml").is_file()
    assert (target / "backend" / "app" / "version.py").is_file()
    assert (target / "frontend" / "package.json").is_file()

    excluded_paths = [
        ".claude",
        ".codex",
        ".cursor",
        ".gemini",
        ".antigravity-cli",
        ".env.template",
        ".gitea",
        "OPEN_SOURCE.md",
        "artifacts",
        "bugs",
        "debugs",
        "docker-compose.prod.yml",
        "docs/DESIGN.md",
        "docs/analysis",
        "docs/blog",
        "docs/evaluation-reports",
        "docs/performance-tuning",
        "docs/superpowers",
        "dogfood-output",
        "implementations",
        "reports",
        "research",
        "scripts/deploy-production.sh",
        "scripts/sync-to-github.sh",
        "skills",
        "spikes",
        "todos",
    ]
    for relative_path in excluded_paths:
        assert not (target / relative_path).exists(), relative_path

    script_names = {path.name for path in (target / "scripts").glob("*.py")}
    assert not any(name.startswith("acas_") for name in script_names)
    assert not any(name.startswith("generate_acas_") for name in script_names)
    assert not any(name.startswith("migrate_acas_") for name in script_names)
    assert not any(name.startswith("test_acas_") for name in script_names)
