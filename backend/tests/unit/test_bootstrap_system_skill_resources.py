from app.services.bootstrap.installer import client_app_file_contents


def test_client_bundle_contains_builtin_system_skill_resources() -> None:
    files = client_app_file_contents()
    expected = {
        "resources/system_skills/agent-creator/SKILL.md",
        "resources/system_skills/agent-creator/agents/openai.yaml",
        "resources/system_skills/artifact-plugin-creator/SKILL.md",
        "resources/system_skills/artifact-plugin-creator/agents/openai.yaml",
        "resources/system_skills/skill-creator/SKILL.md",
        "resources/system_skills/skill-creator/agents/openai.yaml",
        "contexts/agent_profiles/infrastructure/builtin_system_skill_types.py",
        "resources/system_skills/agent-trace-graph/SKILL.md",
        "resources/system_skills/agent-trace-graph/agents/openai.yaml",
        "resources/system_skills/agent-trace-graph/scripts/render.py",
        "resources/system_skills/web-terminal-git-worktree/SKILL.md",
        "resources/system_skills/web-terminal-git-worktree/agents/openai.yaml",
        "resources/system_skills/web-terminal-git-worktree/scripts/setup-git-worktree.sh",
        "resources/system_skills/web-terminal-git-worktree/scripts/init-worktree.sh",
        "resources/system_skills/web-terminal-git-worktree/scripts/merge-agent-branch.py",
        "resources/system_skills/web-terminal-git-worktree/scripts/merge_agent_validation.py",
        "resources/system_skills/web-terminal-git-worktree/scripts/register-worktree.sh",
        "resources/system_skills/web-terminal-git-worktree/scripts/remove-worktree.sh",
    }

    assert expected <= set(files)
