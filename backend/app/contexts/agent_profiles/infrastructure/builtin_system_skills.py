from __future__ import annotations

import shutil
from pathlib import Path
from typing import AbstractSet, Callable, Mapping, TypeVar

from app.contexts.agent_profiles.infrastructure.builtin_system_skill_resources import (
    resource_skill_files,
)
from app.contexts.agent_profiles.infrastructure.builtin_system_skill_types import (
    BuiltinSystemSkill,
    BuiltinSystemSkillFile,
)

T = TypeVar("T")


WEB_TERMINAL_ACP_OPS_SKILL_ID = "web-terminal-acp-ops"
AGENT_TRACE_GRAPH_SKILL_ID = "agent-trace-graph"
WEB_TERMINAL_GIT_WORKTREE_SKILL_ID = "web-terminal-git-worktree"
AGENT_CREATOR_SKILL_ID = "agent-creator"
ARTIFACT_PLUGIN_CREATOR_SKILL_ID = "artifact-plugin-creator"
SKILL_CREATOR_SKILL_ID = "skill-creator"
RESOURCE_SKILL_EXECUTABLE_PATHS = {
    AGENT_TRACE_GRAPH_SKILL_ID: {"scripts/render.py"},
    WEB_TERMINAL_ACP_OPS_SKILL_ID: {"scripts/web-terminal-acp-ops.py"},
    WEB_TERMINAL_GIT_WORKTREE_SKILL_ID: {
        "scripts/init-worktree.sh",
        "scripts/merge-agent-branch.py",
        "scripts/register-worktree.sh",
        "scripts/remove-worktree.sh",
    },
}

AGENT_CREATOR_SKILL = BuiltinSystemSkill(AGENT_CREATOR_SKILL_ID, ())
ARTIFACT_PLUGIN_CREATOR_SKILL = BuiltinSystemSkill(ARTIFACT_PLUGIN_CREATOR_SKILL_ID, ())
SKILL_CREATOR_SKILL = BuiltinSystemSkill(SKILL_CREATOR_SKILL_ID, ())
WEB_TERMINAL_ACP_OPS_SKILL = BuiltinSystemSkill(WEB_TERMINAL_ACP_OPS_SKILL_ID, ())
AGENT_TRACE_GRAPH_SKILL = BuiltinSystemSkill(AGENT_TRACE_GRAPH_SKILL_ID, ())
WEB_TERMINAL_GIT_WORKTREE_SKILL = BuiltinSystemSkill(WEB_TERMINAL_GIT_WORKTREE_SKILL_ID, ())

BUILTIN_SYSTEM_SKILLS = (
    AGENT_CREATOR_SKILL,
    AGENT_TRACE_GRAPH_SKILL,
    ARTIFACT_PLUGIN_CREATOR_SKILL,
    SKILL_CREATOR_SKILL,
    WEB_TERMINAL_ACP_OPS_SKILL,
    WEB_TERMINAL_GIT_WORKTREE_SKILL,
)


def builtin_system_skills() -> tuple[BuiltinSystemSkill, ...]:
    return BUILTIN_SYSTEM_SKILLS


def builtin_system_skill(skill_id: str) -> BuiltinSystemSkill | None:
    return next((skill for skill in BUILTIN_SYSTEM_SKILLS if skill.id == skill_id), None)


def builtin_system_skill_config_items(
    item_factory: Callable[[str, str, bool, str | None, str], T],
    name_from_skill_text: Callable[[str], str | None],
) -> list[T]:
    return [
        item_factory(
            skill.id,
            name_from_skill_text(builtin_system_skill_file_content(skill.id, "SKILL.md") or "")
            or skill.id,
            True,
            None,
            "system_builtin",
        )
        for skill in builtin_system_skills()
    ]


def materialize_builtin_system_skills(
    managed_root: Path,
    skills_directory: str,
    write_text_file: Callable[[Path, str], None],
    *,
    enabled_by_id: Mapping[str, bool] | None = None,
    preserve_existing: bool = False,
    preserve_ids: AbstractSet[str] | None = None,
) -> None:
    for skill in builtin_system_skills():
        active_root = managed_root / skills_directory / skill.id
        disabled_root = managed_root / f"{skills_directory}.disabled" / skill.id
        enabled = (enabled_by_id or {}).get(skill.id, True)
        if skill.id in (preserve_ids or set()) and (active_root.exists() or disabled_root.exists()):
            continue
        if preserve_existing and enabled and (active_root.exists() or disabled_root.exists()):
            continue
        if preserve_existing and not enabled:
            _remove_tree_or_file(active_root)
            if disabled_root.exists():
                continue
        target_root = active_root if enabled else disabled_root
        _remove_tree_or_file(active_root)
        _remove_tree_or_file(disabled_root)
        for file in builtin_system_skill_files(skill):
            target = target_root / file.path
            write_text_file(target, file.content)
            if file.executable:
                target.chmod(target.stat().st_mode | 0o111)


def builtin_system_skill_files(skill: BuiltinSystemSkill) -> tuple[BuiltinSystemSkillFile, ...]:
    if skill.files:
        return skill.files
    if skill in BUILTIN_SYSTEM_SKILLS:
        return resource_skill_files(
            skill.id,
            BuiltinSystemSkillFile,
            executable_paths=RESOURCE_SKILL_EXECUTABLE_PATHS.get(skill.id, set()),
        )
    return ()


def builtin_system_skill_file_content(skill_id: str, path: str) -> str | None:
    skill = builtin_system_skill(skill_id)
    if skill is None:
        return None
    for file in builtin_system_skill_files(skill):
        if file.path == path:
            return file.content
    return None


def _remove_tree_or_file(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink(missing_ok=True)
