from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.contexts.agent_profiles.application.manifest_service import (
    AgentProfileManifest,
    now_iso,
    read_manifest,
    write_manifest,
)
from app.contexts.agent_profiles.infrastructure import builtin_profiles, profile_store
from app.contexts.agent_profiles.infrastructure.builtin_profile_specs import BUILTIN_PROFILE_SPECS
from app.contexts.agent_profiles.infrastructure.profile_settings_repository import agent_profiles_root
from app.platform.ui_setting_files import file_tree_payload, restore_file_tree_payload

AGENT_PROFILE_BUNDLE_KIND = "web-terminal-agent-profile"
AGENT_PROFILE_BUNDLE_VERSION = 1


def export_agent_profile_bundle(profile_id: str, *, home: Path | None = None) -> dict[str, object]:
    user_home = home or Path.home()
    if builtin_profiles.is_builtin_profile_id(profile_id):
        profile = builtin_profiles.get_builtin_agent_profile(profile_id)
        if profile is None:
            raise ValueError(f"agent profile not found: {profile_id}")
        return _bundle(profile, _builtin_profile_files_payload(profile_id), origin="built_in")

    profile = profile_store.get_agent_profile(profile_id, home=user_home)
    root = agent_profiles_root(user_home) / profile_id
    return _bundle(profile, file_tree_payload(root), origin="managed")


def import_agent_profile_bundle(payload: object, *, home: Path | None = None) -> profile_store.AgentProfile:
    if not isinstance(payload, dict):
        raise ValueError("agent profile import payload must be an object")
    if payload.get("kind") != AGENT_PROFILE_BUNDLE_KIND:
        raise ValueError("unsupported agent profile import payload")
    files = payload.get("files")
    if not isinstance(files, dict):
        raise ValueError("agent profile import payload is missing files")

    user_home = home or Path.home()
    profile_id = uuid4().hex
    root = agent_profiles_root(user_home) / profile_id
    try:
        restore_file_tree_payload(root, files)
        manifest = _imported_manifest(root, profile_id)
        write_manifest(root, manifest)
        if not (root / profile_store.COMMON_AGENT_MD).is_file():
            profile_store._write_agent_md(root, "")
        return profile_store.get_agent_profile(profile_id, home=user_home)
    except Exception:
        if root.exists() or root.is_symlink():
            if root.is_dir() and not root.is_symlink():
                shutil.rmtree(root)
            else:
                root.unlink()
        raise


def _bundle(
    profile: profile_store.AgentProfile,
    files: dict[str, object],
    *,
    origin: str,
) -> dict[str, object]:
    return {
        "kind": AGENT_PROFILE_BUNDLE_KIND,
        "version": AGENT_PROFILE_BUNDLE_VERSION,
        "origin": origin,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "default_agent_client": profile.default_agent_client,
            "agent_md": profile.agent_md,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        },
        "files": files,
    }


def _builtin_profile_files_payload(profile_id: str) -> dict[str, object]:
    name, description, agent_md, skills = BUILTIN_PROFILE_SPECS[profile_id]
    now = now_iso()
    manifest = AgentProfileManifest.new(
        profile_id=profile_id,
        name=name,
        description=description,
        default_agent_client="codex",
        client_configs={},
        now=now,
    )
    text_files = {
        "profile.json": json.dumps(
            manifest.to_dict(),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        profile_store.COMMON_AGENT_MD: agent_md,
    }
    for skill_id, skill_md in skills:
        text_files[f"{profile_store.COMMON_SKILLS_DIR}/{skill_id}/SKILL.md"] = skill_md
    return _text_file_tree_payload(text_files)


def _text_file_tree_payload(files: dict[str, str]) -> dict[str, object]:
    return {
        "version": 1,
        "files": [
            {
                "path": path,
                "content_b64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "mode": 0o644,
            }
            for path, content in sorted(files.items())
        ],
    }


def _imported_manifest(root: Path, profile_id: str) -> AgentProfileManifest:
    imported = read_manifest(root)
    profile_record = _profile_record(root)
    now = now_iso()
    return AgentProfileManifest.new(
        profile_id=profile_id,
        name=_string(profile_record.get("name")) or imported.name,
        description=_string(profile_record.get("description")) or imported.description,
        default_agent_client=_string(profile_record.get("default_agent_client"))
        or imported.default_agent_client,
        client_configs=imported.client_configs,
        now=now,
    )


def _profile_record(root: Path) -> dict[str, Any]:
    path = root / "profile.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return record if isinstance(record, dict) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
