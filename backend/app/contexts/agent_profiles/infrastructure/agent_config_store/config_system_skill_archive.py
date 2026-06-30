from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

from .config_items import _validate_path_item_id
from .config_system import (
    SYSTEM_DISABLED_SKILLS_DIR,
    SYSTEM_SKILLS_DIR,
    _system_builtin_item_for_id,
    _system_config_root,
)


def system_skill_zip_bytes(skill_id: str, *, home: Path | None = None) -> bytes:
    _validate_path_item_id(skill_id)
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    skill_root = root / SYSTEM_SKILLS_DIR / skill_id
    if not skill_root.is_dir():
        skill_root = root / SYSTEM_DISABLED_SKILLS_DIR / skill_id
    if skill_root.is_dir():
        return _skill_directory_zip_bytes(skill_id, skill_root)
    archive = _builtin_system_skill_zip_bytes(skill_id, user_home)
    if archive is None:
        raise ValueError(f"system skill not found: {skill_id}")
    return archive


def _skill_directory_zip_bytes(skill_id: str, skill_root: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(candidate for candidate in skill_root.rglob("*") if candidate.is_file()):
            archive.write(
                path, PurePosixPath(skill_id, path.relative_to(skill_root).as_posix()).as_posix()
            )
    return buffer.getvalue()


def _builtin_system_skill_zip_bytes(skill_id: str, home: Path) -> bytes | None:
    item = _system_builtin_item_for_id("skills", skill_id, home=home)
    if item is None:
        return None
    files = _builtin_profile_skill_zip_files(skill_id)
    if files is None:
        files = _packaged_builtin_system_skill_zip_files(skill_id)
    if files is None and item.path is not None:
        path = Path(item.path)
        if path.is_dir():
            return _skill_directory_zip_bytes(skill_id, path)
    if files is None:
        return None
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path, content in sorted(files.items()):
            archive.writestr(PurePosixPath(skill_id, relative_path).as_posix(), content)
    return buffer.getvalue()


def _builtin_profile_skill_zip_files(skill_id: str) -> dict[str, str] | None:
    from app.contexts.agent_profiles.infrastructure import builtin_profile_specs

    content_by_id = {
        profile_skill_id: skill_md
        for _name, _description, _agent_md, profile_skills in builtin_profile_specs.BUILTIN_PROFILE_SPECS.values()
        for profile_skill_id, skill_md in profile_skills
    }
    skill_md = content_by_id.get(skill_id)
    if skill_md is not None:
        return {"SKILL.md": skill_md}
    return None


def _packaged_builtin_system_skill_zip_files(skill_id: str) -> dict[str, str] | None:
    from app.contexts.agent_profiles.infrastructure import builtin_system_skills

    skill = builtin_system_skills.builtin_system_skill(skill_id)
    if skill is None:
        return None
    return {
        file.path: file.content
        for file in builtin_system_skills.builtin_system_skill_files(skill)
    }
