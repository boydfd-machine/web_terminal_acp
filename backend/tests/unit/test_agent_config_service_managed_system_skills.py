import os
from pathlib import Path

from tests.unit.test_agent_config_service_support import (
    agent_config_service,
    agent_profile_service,
    section_items,
    write_skill,
)

MANAGED_SCAN_LIMIT = 64


def write_packaged_skill(root: Path, name: str) -> None:
    write_skill(root, name)
    agents = root / name / "agents"
    agents.mkdir()
    (agents / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")


def test_managed_agent_home_skill_is_available_to_profile_config_and_dispatch(
    tmp_path: Path,
) -> None:
    source_skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "source-window"
        / "skills"
        / "image-to-ppt"
    )
    write_packaged_skill(source_skill.parent, "image-to-ppt")

    system_config = agent_config_service.list_system_agent_config(home=tmp_path)

    system_skill = section_items(system_config, "skills")["image-to-ppt"]
    assert system_skill.origin == "system_builtin"
    assert system_skill.path == str(source_skill)
    assert system_skill.enabled is True

    profile = agent_profile_service.create_agent_profile(
        name="Builder",
        default_agent_client="codex",
        home=tmp_path,
    )
    profile_config = agent_profile_service.list_agent_profile_config(
        profile.id,
        "codex",
        home=tmp_path,
    )
    profile_skill = section_items(profile_config, "skills")["image-to-ppt"]
    assert profile_skill.enabled is True
    assert profile_skill.path == str(source_skill)

    agent_profile_service.materialize_agent_profile_for_window(
        profile.id,
        "codex",
        window_id="target-window",
        home=tmp_path,
    )

    target_skill = (
        tmp_path
        / ".web-terminal-acp"
        / "codex-homes"
        / "target-window"
        / "skills"
        / "image-to-ppt"
    )
    assert (target_skill / "SKILL.md").is_file()
    assert target_skill.is_symlink()
    assert target_skill.resolve() == source_skill


def test_managed_agent_home_skill_respects_system_default_disable(tmp_path: Path) -> None:
    write_packaged_skill(
        tmp_path / ".web-terminal-acp" / "codex-homes" / "source-window" / "skills",
        "image-to-ppt",
    )

    agent_config_service.set_system_agent_config_item_enabled(
        "skills",
        "image-to-ppt",
        False,
        home=tmp_path,
    )
    agent_config_service.install_system_config_for_agent_window(
        "codex",
        window_id="target-window",
        home=tmp_path,
    )

    target_home = tmp_path / ".web-terminal-acp" / "codex-homes" / "target-window"
    assert not (target_home / "skills" / "image-to-ppt").exists()
    assert (target_home / "skills.disabled" / "image-to-ppt" / "SKILL.md").is_file()


def test_managed_agent_home_skill_scan_is_bounded_to_recent_homes(tmp_path: Path) -> None:
    root = tmp_path / ".web-terminal-acp" / "codex-homes"
    for index in range(MANAGED_SCAN_LIMIT + 1):
        home = root / f"old-window-{index:03d}"
        write_packaged_skill(home / "skills", f"old-skill-{index:03d}")
        timestamp = 1_700_000_000 + index
        home.touch()
        os.utime(home, (timestamp, timestamp))
    recent = root / "recent-window"
    write_packaged_skill(recent / "skills", "image-to-ppt")
    recent.touch()
    os.utime(recent, (1_800_000_000, 1_800_000_000))

    config = agent_config_service.list_system_agent_config(home=tmp_path)
    skills = section_items(config, "skills")

    assert "image-to-ppt" in skills
    assert "old-skill-000" not in skills


def test_system_agent_config_files_payload_restores_disabled_skill(tmp_path: Path) -> None:
    skill_root = tmp_path / ".web-terminal-acp" / "system-config" / "skills.disabled" / "image-to-ppt"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("---\nname: Image to PPT\n---\n", encoding="utf-8")
    (skill_root / "icon.bin").write_bytes(b"\x00ppt\xff")

    payload = agent_config_service.system_agent_config_files_payload(home=tmp_path)
    assert {
        item["path"]
        for item in payload["files"]
    } == {"skills.disabled/image-to-ppt/SKILL.md", "skills.disabled/image-to-ppt/icon.bin"}

    restored_home = tmp_path / "restored"
    agent_config_service.restore_system_agent_config_files_payload(payload, home=restored_home)

    restored = restored_home / ".web-terminal-acp" / "system-config" / "skills.disabled" / "image-to-ppt"
    assert (restored / "SKILL.md").read_text(encoding="utf-8") == "---\nname: Image to PPT\n---\n"
    assert (restored / "icon.bin").read_bytes() == b"\x00ppt\xff"


def test_system_agent_config_files_payload_skips_files_deleted_during_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_root = tmp_path / ".web-terminal-acp" / "system-config" / "skills" / "image-to-ppt"
    skill_root.mkdir(parents=True)
    skill_md = skill_root / "SKILL.md"
    transient = skill_root / "rubrics" / "principles.md"
    transient.parent.mkdir()
    skill_md.write_text("---\nname: Image to PPT\n---\n", encoding="utf-8")
    transient.write_text("temporary", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self == transient:
            raise FileNotFoundError(self)
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    payload = agent_config_service.system_agent_config_files_payload(home=tmp_path)

    assert [item["path"] for item in payload["files"]] == ["skills/image-to-ppt/SKILL.md"]
