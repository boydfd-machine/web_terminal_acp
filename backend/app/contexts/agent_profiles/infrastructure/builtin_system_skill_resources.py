from __future__ import annotations

from importlib import resources
from typing import Protocol


class BuiltinSystemSkillFileFactory(Protocol):
    def __call__(self, path: str, content: str, executable: bool = False): ...


def resource_skill_files(
    skill_id: str,
    file_factory: BuiltinSystemSkillFileFactory,
    *,
    executable_paths: set[str] | None = None,
) -> tuple[object, ...]:
    root = resources.files("app.resources.system_skills").joinpath(skill_id)
    executable = executable_paths or set()
    return tuple(
        file_factory(
            relative_path,
            traversable.read_text(encoding="utf-8"),
            relative_path in executable,
        )
        for relative_path, traversable in sorted(_iter_resource_files(root), key=lambda item: item[0])
    )


def _iter_resource_files(root) -> list[tuple[str, object]]:
    files: list[tuple[str, object]] = []
    pending = [(root, "")]
    while pending:
        current, prefix = pending.pop()
        for child in current.iterdir():
            if child.name == "__pycache__" or child.name.endswith((".pyc", ".pyo")):
                continue
            relative = f"{prefix}{child.name}"
            if child.is_dir():
                pending.append((child, f"{relative}/"))
            elif child.is_file():
                files.append((relative, child))
    return files
