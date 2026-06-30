import json
from pathlib import Path

import pytest

from app.services import agent_profiles as agent_profile_service


def test_agent_profile_update_preserves_manifest_identity_and_cleans_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter([
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
    ])
    monkeypatch.setattr(agent_profile_service, "now_iso", lambda: next(timestamps))

    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        description=" Initial description ",
        default_agent_client="codex",
        home=tmp_path,
    )
    profile_root = tmp_path / ".web-terminal-acp" / "agents" / profile.id
    original_manifest = json.loads((profile_root / "profile.json").read_text(encoding="utf-8"))

    updated = agent_profile_service.update_agent_profile(
        profile.id,
        name=" Renamed ",
        description="   ",
        home=tmp_path,
    )
    updated_manifest = json.loads((profile_root / "profile.json").read_text(encoding="utf-8"))

    assert updated.id == profile.id
    assert updated.name == "Renamed"
    assert updated.description is None
    assert updated_manifest["id"] == original_manifest["id"]
    assert updated_manifest["created_at"] == original_manifest["created_at"]
    assert updated_manifest["updated_at"] != original_manifest["updated_at"]
