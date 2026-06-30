from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinSystemSkillFile:
    path: str
    content: str
    executable: bool = False


@dataclass(frozen=True)
class BuiltinSystemSkill:
    id: str
    files: tuple[BuiltinSystemSkillFile, ...]

    @property
    def skill_md(self) -> str:
        for file in self.files:
            if file.path == "SKILL.md":
                return file.content
        raise ValueError(f"built-in system skill missing SKILL.md: {self.id}")
