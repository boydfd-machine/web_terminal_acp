import io
import zipfile
from pathlib import Path

import pytest
import yaml

from app.contexts.agent_profiles.infrastructure import builtin_system_skills
from app.services import agent_config as agent_config_service
from tests.unit.test_agent_config_service_support import section_items


def _skill_archive(skill_id: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
    return buffer.getvalue()


def _skill_frontmatter(skill_md: str) -> dict[str, object]:
    assert skill_md.startswith("---\n")
    _prefix, metadata, _body = skill_md.split("---", 2)
    parsed = yaml.safe_load(metadata)
    assert isinstance(parsed, dict)
    return parsed


def test_web_terminal_acp_ops_is_editable_system_builtin(tmp_path: Path) -> None:
    config = agent_config_service.list_system_agent_config(home=tmp_path)
    skills = section_items(config, "skills")
    assert skills["web-terminal-acp-ops"].origin == "system_builtin"
    assert set(skills) == {
        "agent-creator",
        "agent-trace-graph",
        "artifact-plugin-creator",
        "skill-creator",
        "web-terminal-acp-ops",
        "web-terminal-git-worktree",
    }

    detail = agent_config_service.system_skill_detail("web-terminal-acp-ops", home=tmp_path)
    files = {file.path: file for file in detail.files}
    assert detail.editable is True
    assert detail.origin == "system_builtin"
    assert detail.overridden is False
    assert {"SKILL.md", "scripts/web-terminal-acp-ops.py", "agents/openai.yaml"} <= set(files)
    skill_md = files["SKILL.md"].content or ""
    cli = files["scripts/web-terminal-acp-ops.py"].content or ""
    openai_yaml = files["agents/openai.yaml"].content or ""
    frontmatter = _skill_frontmatter(skill_md)
    assert frontmatter["name"] == "web-terminal-acp-ops"
    assert "operate Web Terminal ACP" in str(frontmatter["description"])
    assert "WEB_TERMINAL_AGENT_OPS_TOKEN" in skill_md
    assert "read-project-todo" in skill_md
    assert "create-project-todo" in skill_md
    assert "patch-project-todo" in skill_md
    assert "dispatch-project-todo" in skill_md
    assert "read-agent-preview" in skill_md
    assert "read-artifact" in skill_md
    assert "read-card-artifact" in skill_md
    assert "upsert-artifact-plugin-preview" in skill_md
    assert "--compact read-project-todo <todo-id>" in skill_md
    assert "argparse rejects them after the subcommand" in skill_md
    assert "def main(" in cli
    assert "/api/agent-ops" in cli
    assert "web-terminal-acp-mcp" not in skill_md
    assert "web-terminal-acp-mcp" not in openai_yaml

    overridden = agent_config_service.install_system_skill_from_zip(
        "web-terminal-acp-ops",
        _skill_archive("web-terminal-acp-ops"),
        home=tmp_path,
    )
    assert section_items(overridden, "skills")["web-terminal-acp-ops"].origin == "system_config"


def test_agent_trace_graph_is_editable_system_builtin(tmp_path: Path) -> None:
    config = agent_config_service.list_system_agent_config(home=tmp_path)
    skills = section_items(config, "skills")
    assert skills["agent-trace-graph"].origin == "system_builtin"

    detail = agent_config_service.system_skill_detail("agent-trace-graph", home=tmp_path)
    files = {file.path: file for file in detail.files}

    assert detail.editable is True
    assert detail.origin == "system_builtin"
    assert detail.overridden is False
    assert {"SKILL.md", "scripts/render.py", "agents/openai.yaml"} <= set(files)
    skill_md = files["SKILL.md"].content or ""
    assert "Agent Trace Graph" in skill_md
    assert "python3 scripts/render.py" in skill_md
    assert "def main(" in (files["scripts/render.py"].content or "")
    assert "render.py trace.json" in (files["scripts/render.py"].content or "")

    overridden = agent_config_service.install_system_skill_from_zip(
        "agent-trace-graph",
        _skill_archive("agent-trace-graph"),
        home=tmp_path,
    )
    assert section_items(overridden, "skills")["agent-trace-graph"].origin == "system_config"


def test_agent_trace_graph_system_builtin_downloads_as_zip(tmp_path: Path) -> None:
    archive = agent_config_service.system_skill_zip_bytes("agent-trace-graph", home=tmp_path)

    with zipfile.ZipFile(io.BytesIO(archive)) as downloaded:
        names = set(downloaded.namelist())
        assert {
            "agent-trace-graph/SKILL.md",
            "agent-trace-graph/scripts/render.py",
            "agent-trace-graph/agents/openai.yaml",
        } <= names
        skill_md = downloaded.read("agent-trace-graph/SKILL.md").decode("utf-8")
        render_script = downloaded.read("agent-trace-graph/scripts/render.py").decode("utf-8")

    assert "Agent Trace Graph" in skill_md
    assert "def main(" in render_script


def test_web_terminal_git_worktree_is_editable_system_builtin(tmp_path: Path) -> None:
    config = agent_config_service.list_system_agent_config(home=tmp_path)
    skills = section_items(config, "skills")
    assert skills["web-terminal-git-worktree"].origin == "system_builtin"

    detail = agent_config_service.system_skill_detail("web-terminal-git-worktree", home=tmp_path)
    files = {file.path: file for file in detail.files}

    assert detail.editable is True
    assert detail.origin == "system_builtin"
    assert detail.overridden is False
    assert {
        "SKILL.md",
        "scripts/init-worktree.sh",
        "scripts/merge-agent-branch.py",
        "scripts/merge_agent_validation.py",
        "scripts/register-worktree.sh",
        "scripts/remove-worktree.sh",
        "agents/openai.yaml",
    } <= set(files)
    skill_md = files["SKILL.md"].content or ""
    frontmatter = _skill_frontmatter(skill_md)
    assert frontmatter["name"] == "web-terminal-git-worktree"
    assert "WEB_TERMINAL_WINDOW_ID" in str(frontmatter["description"])
    assert "Migration Conflict Gate" in skill_md
    assert "git merge main" in skill_md
    assert "sqlite+aiosqlite" in skill_md
    assert 'python3 "$SKILL_DIR/scripts/merge-agent-branch.py"' in skill_md
    assert "Full tests before merge" in skill_md
    assert "cd backend && uv run pytest tests -n 8 -q" in skill_md
    assert "run_required_test_suites" in (files["scripts/merge-agent-branch.py"].content or "")
    validation_script = files["scripts/merge_agent_validation.py"].content or ""
    assert "required_test_suites" in validation_script
    assert '["uv", "run", "pytest", "tests", "-n", "8", "-q"]' in validation_script
    assert "def main(" in (files["scripts/merge-agent-branch.py"].content or "")
    assert ".cursor/skills/web-terminal-git-worktree" not in skill_md
    assert "web-terminal-git-worktree" in (files["agents/openai.yaml"].content or "")

    overridden = agent_config_service.install_system_skill_from_zip(
        "web-terminal-git-worktree",
        _skill_archive("web-terminal-git-worktree"),
        home=tmp_path,
    )
    assert section_items(overridden, "skills")["web-terminal-git-worktree"].origin == "system_config"


@pytest.mark.parametrize(
    "skill_id, expected_text",
    [
        ("agent-creator", "Agent Creator"),
        ("artifact-plugin-creator", "Artifact Plugin Creator"),
        ("skill-creator", "Skill Creator"),
    ],
)
def test_creator_skills_are_editable_system_builtins(
    tmp_path: Path,
    skill_id: str,
    expected_text: str,
) -> None:
    detail = agent_config_service.system_skill_detail(skill_id, home=tmp_path)
    files = {file.path: file for file in detail.files}

    assert detail.editable is True
    assert detail.origin == "system_builtin"
    assert detail.overridden is False
    assert {"SKILL.md", "agents/openai.yaml"} <= set(files)
    assert expected_text in (files["SKILL.md"].content or "")


@pytest.mark.parametrize("skill_id", ["debug-expert", "tdd", "deep-research"])
def test_developer_profile_skills_are_not_system_builtins(tmp_path: Path, skill_id: str) -> None:
    with pytest.raises(ValueError, match=f"system skill not found: {skill_id}"):
        agent_config_service.system_skill_detail(skill_id, home=tmp_path)


def test_system_builtin_skills_materialize_for_agent_windows(tmp_path: Path) -> None:
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "window-1"
        / "skills"
        / "web-terminal-acp-ops"
    )
    script = skill / "scripts" / "web-terminal-acp-ops.py"
    assert (skill / "SKILL.md").is_file()
    assert (skill / "agents" / "openai.yaml").is_file()
    assert script.is_file()
    assert script.stat().st_mode & 0o111

    trace_skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "window-1"
        / "skills"
        / "agent-trace-graph"
    )
    trace_script = trace_skill / "scripts" / "render.py"
    assert (trace_skill / "SKILL.md").is_file()
    assert (trace_skill / "agents" / "openai.yaml").is_file()
    assert trace_script.is_file()
    assert trace_script.stat().st_mode & 0o111

    worktree_skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "window-1"
        / "skills"
        / "web-terminal-git-worktree"
    )
    for script_name in (
        "init-worktree.sh",
        "merge-agent-branch.py",
        "register-worktree.sh",
        "remove-worktree.sh",
    ):
        script = worktree_skill / "scripts" / script_name
        assert script.is_file()
        assert script.stat().st_mode & 0o111
    assert (worktree_skill / "scripts" / "merge_agent_validation.py").is_file()
    assert (worktree_skill / "agents" / "openai.yaml").is_file()

    for skill_id in ("agent-creator", "artifact-plugin-creator", "skill-creator"):
        assert (
            tmp_path
            / ".web-terminal-acp"
            / "codex-homes"
            / "window-1"
            / "skills"
            / skill_id
            / "SKILL.md"
        ).is_file()


def test_system_builtin_skill_edit_preserves_executable_files(tmp_path: Path) -> None:
    agent_config_service.update_system_skill_file(
        "web-terminal-acp-ops",
        "SKILL.md",
        "---\nname: custom-web-terminal-acp-ops\n---\n",
        home=tmp_path,
    )

    script = (
        tmp_path
        / ".web-terminal-acp"
        / "system-config"
        / "skills"
        / "web-terminal-acp-ops"
        / "scripts"
        / "web-terminal-acp-ops.py"
    )
    assert script.is_file()
    assert script.stat().st_mode & 0o111


def test_system_builtin_skills_replace_stale_materialized_copy(tmp_path: Path) -> None:
    stale_skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "window-1"
        / "skills"
        / "web-terminal-acp-ops"
    )
    stale_script = stale_skill / "scripts" / "web-terminal-acp-ops.py"
    stale_script.parent.mkdir(parents=True)
    (stale_skill / "SKILL.md").write_text(
        "description: stale MCP copy\nweb-terminal-acp-mcp\n",
        encoding="utf-8",
    )
    stale_script.write_text('SERVER_ID = "web-terminal-acp-mcp"\n', encoding="utf-8")

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    skill_md = (stale_skill / "SKILL.md").read_text(encoding="utf-8")
    script = stale_script.read_text(encoding="utf-8")
    assert "WEB_TERMINAL_AGENT_OPS_TOKEN" in skill_md
    assert "web-terminal-acp-mcp" not in skill_md
    assert "/api/agent-ops" in script
    assert "web-terminal-acp-mcp" not in script
    assert stale_script.stat().st_mode & 0o111


def test_disabled_system_builtin_skill_materializes_under_disabled_skills(tmp_path: Path) -> None:
    agent_config_service.set_system_agent_config_item_enabled(
        "skills",
        "agent-trace-graph",
        False,
        home=tmp_path,
    )

    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )

    root = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    assert not (root / "skills" / "agent-trace-graph").exists()
    assert (root / "skills.disabled" / "agent-trace-graph" / "SKILL.md").is_file()
