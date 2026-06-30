import json

from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

from threading import Event

import pytest

from app.services.agent_config import (
    AgentConfigItemSelection,
    AgentConfigSectionSelection,
    AgentConfigSelection,
    apply_agent_config_selection,
    list_agent_config,
    set_agent_config_item_enabled,
)

from app.services import agent_config as agent_config_service

from app.services import agent_profiles as agent_profile_service

def section_items(config, section: str):
    for candidate in config.sections:
        if candidate.id == section:
            return {item.id: item for item in candidate.items}
    raise AssertionError(f"missing section: {section}")

def write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

__all__ = [name for name in globals() if not name.startswith("__")]
