import json
from pathlib import Path

from app.contexts.agent_profiles.infrastructure import builtin_profiles
from tests.unit.test_agent_config_service_support import section_items, write_skill


def _write_codex_mcp(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\nargs = ["ok"]\n',
        encoding="utf-8",
    )


def test_developer_config_enables_development_skills(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    _write_codex_mcp(codex_home)

    config = builtin_profiles.builtin_profile_config("builtin/developer", "codex", home=tmp_path)

    assert config is not None
    skills = section_items(config, "skills")
    mcp = section_items(config, "mcp")
    assert skills["frontend-development"].enabled is True
    assert skills["backend-development"].enabled is True
    assert skills["tdd"].enabled is True
    assert skills["deep-research"].enabled is True
    assert skills["docker"].enabled is False
    assert mcp["filesystem"].enabled is False


def test_developer_materialization_writes_agent_prompt_and_skills(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    write_skill(codex_home / "skills", "docker")
    _write_codex_mcp(codex_home)

    config = builtin_profiles.materialize_builtin_profile_for_window(
        "builtin/developer",
        "codex",
        window_id="window-developer",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-developer"
    disabled_mcp = json.loads((managed / "mcp.disabled.json").read_text(encoding="utf-8"))
    agent_prompt = (managed / "AGENTS.md").read_text(encoding="utf-8")
    frontend_skill = (managed / "skills" / "frontend-development" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    backend_skill = (managed / "skills" / "backend-development" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert config is not None
    assert agent_prompt.startswith("# Built-in Developer Agent")
    assert "Use `frontend-development`" in agent_prompt
    assert "Use `backend-development`" in agent_prompt
    assert "client version sources" in agent_prompt
    assert "bootstrap bundle dependency tests" in agent_prompt
    assert "name: frontend-development" in frontend_skill
    assert "React 18, TypeScript, Vite" in frontend_skill
    assert "backend/app/version.py" in frontend_skill
    assert "name: backend-development" in backend_skill
    assert "context-based architecture" in backend_skill
    assert "bootstrap_installer.py::client_app_file_contents()" in backend_skill
    assert "test_client_app_file_contents_includes_file_level_app_imports" in backend_skill
    assert (managed / "skills" / "tdd" / "SKILL.md").is_file()
    assert (managed / "skills" / "deep-research" / "SKILL.md").is_file()
    assert not (managed / "skills" / "docker").exists()
    assert (managed / "skills.disabled" / "docker" / "SKILL.md").is_file()
    assert "[mcp_servers.filesystem]" not in (managed / "config.toml").read_text(encoding="utf-8")
    assert "filesystem" in disabled_mcp["mcpServers"]
    skills = section_items(config, "skills")
    assert skills["frontend-development"].enabled is True
    assert skills["backend-development"].enabled is True
