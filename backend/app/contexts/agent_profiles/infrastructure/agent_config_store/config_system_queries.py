from pathlib import Path

from .config_system import list_system_agent_config


def enabled_system_config_skill_ids(home: Path) -> set[str]:
    return {
        item.id
        for section in list_system_agent_config(home=home).sections
        if section.id == "skills"
        for item in section.items
        if item.enabled and item.origin == "system_config"
    }
