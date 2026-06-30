from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contexts.agent_profiles.infrastructure import agent_config_store as agent_config

PROFILE_VERSION = 1
PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class AgentProfileManifest:
    version: int
    id: str
    name: str
    description: str | None
    default_agent_client: agent_config.AgentKind
    client_configs: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def new(
        cls,
        *,
        profile_id: str,
        name: str,
        description: str | None,
        default_agent_client: agent_config.AgentKind,
        client_configs: dict[str, Any],
        now: str,
    ) -> "AgentProfileManifest":
        return cls(
            version=PROFILE_VERSION,
            id=profile_id,
            name=clean_name(name),
            description=clean_description(description),
            default_agent_client=default_agent_client,
            client_configs=client_configs,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, profile_id: str, data: dict[str, Any]) -> "AgentProfileManifest":
        manifest_id = string_value(data.get("id")) or profile_id
        default_agent_client = agent_config.normalize_agent_kind(
            string_value(data.get("default_agent_client")) or "codex"
        )
        client_configs = data.get("client_configs")
        return cls(
            version=int(data.get("version") or PROFILE_VERSION),
            id=manifest_id,
            name=string_value(data.get("name")) or manifest_id,
            description=string_value(data.get("description")),
            default_agent_client=default_agent_client,
            client_configs=client_configs if isinstance(client_configs, dict) else {},
            created_at=string_value(data.get("created_at")) or now_iso(),
            updated_at=string_value(data.get("updated_at")) or now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_agent_client": self.default_agent_client,
            "client_configs": self.client_configs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def with_updates(
        self,
        *,
        name: str | None = None,
        description: str | None | object = None,
        description_set: bool = False,
        default_agent_client: str | None = None,
        updated_at: str,
    ) -> "AgentProfileManifest":
        next_manifest = self
        if name is not None:
            next_manifest = replace(next_manifest, name=clean_name(name))
        if description_set:
            cleaned_description = clean_description(
                description if isinstance(description, str) else None
            )
            next_manifest = replace(
                next_manifest,
                description=cleaned_description,
            )
        if default_agent_client is not None:
            next_manifest = replace(
                next_manifest,
                default_agent_client=agent_config.normalize_agent_kind(default_agent_client),
            )
        return replace(next_manifest, updated_at=updated_at)


def validate_profile_id(profile_id: str) -> None:
    if not profile_id or not PROFILE_ID_PATTERN.fullmatch(profile_id) or profile_id in {".", ".."}:
        raise ValueError(f"invalid agent profile id: {profile_id}")


def read_manifest(root: Path) -> AgentProfileManifest:
    path = root / "profile.json"
    if not path.is_file():
        raise ValueError(f"agent profile manifest not found: {root.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid agent profile manifest: {root.name}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"invalid agent profile manifest: {root.name}")
    return AgentProfileManifest.from_dict(root.name, data)


def write_manifest(root: Path, manifest: AgentProfileManifest) -> None:
    root.mkdir(parents=True, exist_ok=True)
    agent_config._write_text_file_atomic(
        root / "profile.json",
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("agent profile name is required")
    if len(cleaned) > 120:
        raise ValueError("agent profile name is too long")
    return cleaned


def clean_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = description.strip()
    if not cleaned:
        return None
    if len(cleaned) > 500:
        raise ValueError("agent profile description is too long")
    return cleaned


def string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
