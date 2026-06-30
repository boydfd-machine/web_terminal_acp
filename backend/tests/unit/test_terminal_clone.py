import json
import socket
import sqlite3
import tempfile
from pathlib import Path
from uuid import UUID

from app.services.terminal_clone import (
    clone_resume_command,
    clone_window_agent_homes,
    remove_window_agent_homes,
)


SOURCE_WINDOW_ID = UUID("11111111-1111-1111-1111-111111111111")
TARGET_WINDOW_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_clone_window_agent_homes_reuses_codex_session_id_and_rewrites_other_agent_sessions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    old_codex_session = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    old_claude_session = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    _write_codex_session(home, old_codex_session)
    _write_claude_session(home, old_claude_session)
    _write_cursor_store(home)
    _write_antigravity_transcript(home, "old-antigravity-session")
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    assert set(result.cloned_agents) == {"codex", "claude", "cursor", "antigravity"}
    assert result.session_ids["codex"] == old_codex_session
    _assert_target_codex_session(home, old_codex_session)
    assert _target_codex_home(home).joinpath(".web-terminal-cloned-home").is_file()
    _assert_claude_session_rewritten(home, old_claude_session, result.session_ids["claude"])
    _assert_cursor_store_rewritten(home, result.session_ids["cursor"])
    _assert_antigravity_transcript_preserved(home, "old-antigravity-session")
    assert result.resume_commands == {
        "codex": (
            f"codex --dangerously-bypass-approvals-and-sandbox resume {result.session_ids['codex']}"
        ),
        "claude": (
            f"claude --dangerously-skip-permissions --resume {result.session_ids['claude']}"
        ),
        "cursor": f"agent --resume {result.session_ids['cursor']}",
        "antigravity": (
            "agy-p --dangerously-skip-permissions --conversation old-antigravity-session"
        ),
    }


def test_clone_window_agent_homes_preserves_antigravity_conversation_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    _write_antigravity_transcript(home, "antigravity-session-1")
    cache = home / ".web-terminal-acp" / "antigravity-cli-homes" / str(SOURCE_WINDOW_ID) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "last_conversations.json").write_text(
        json.dumps({"/workspace": "antigravity-session-1"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    target_root = home / ".web-terminal-acp" / "antigravity-cli-homes" / str(TARGET_WINDOW_ID)
    assert (target_root / "brain" / "antigravity-session-1").is_dir()
    assert json.loads(
        (target_root / "cache" / "last_conversations.json").read_text(encoding="utf-8")
    ) == {"/workspace": "antigravity-session-1"}
    assert result.session_ids["antigravity"] == "antigravity-session-1"
    assert result.resume_commands["antigravity"].endswith("--conversation antigravity-session-1")


def test_clone_window_agent_homes_uses_antigravity_conversation_for_source_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    _write_antigravity_transcript(home, "workspace-session")
    _write_antigravity_transcript(home, "tmp-session")
    cache = home / ".web-terminal-acp" / "antigravity-cli-homes" / str(SOURCE_WINDOW_ID) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "last_conversations.json").write_text(
        json.dumps(
            {
                "/tmp": "tmp-session",
                "/workspace": "workspace-session",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID, source_cwd="/workspace")

    assert result.session_ids["antigravity"] == "workspace-session"
    assert result.resume_commands["antigravity"].endswith("--conversation workspace-session")


def test_clone_window_agent_homes_ignores_runtime_socket_files(
    monkeypatch,
) -> None:
    with tempfile.TemporaryDirectory(prefix="wt-") as raw_home:
        home = Path(raw_home)
        _write_cursor_store(home)
        socket_path = (
            home
            / ".web-terminal-acp"
            / "cursor-homes"
            / str(SOURCE_WINDOW_ID)
            / "tmp"
            / "worker.sock"
        )
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            unix_socket.bind(str(socket_path))
            monkeypatch.setattr(Path, "home", lambda: home)

            result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)
        finally:
            unix_socket.close()

        target_socket = (
            home
            / ".web-terminal-acp"
            / "cursor-homes"
            / str(TARGET_WINDOW_ID)
            / "tmp"
            / "worker.sock"
        )
        assert result.cloned_agents == ("cursor",)
        assert result.session_ids["cursor"]
        assert not target_socket.exists()
        _assert_cursor_store_rewritten(home, result.session_ids["cursor"])


def test_clone_window_agent_homes_skips_codex_tmp_and_relinks_shared_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    old_codex_session = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_codex_session(home, old_codex_session)
    source_tmp = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(SOURCE_WINDOW_ID)
        / ".tmp"
        / "plugins"
        / ".git"
        / "objects"
        / "pack"
    )
    source_tmp.mkdir(parents=True)
    (source_tmp / "heavy.pack").write_bytes(b"not-session-cache")
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    assert result.cloned_agents == ("codex",)
    assert result.session_ids["codex"] == old_codex_session
    target_tmp = _target_codex_home(home) / ".tmp"
    shared_tmp = home / ".web-terminal-acp" / "shared-cache" / "codex" / "tmp"
    assert target_tmp.is_symlink()
    assert target_tmp.resolve() == shared_tmp
    assert not (shared_tmp / "plugins" / ".git" / "objects" / "pack" / "heavy.pack").exists()
    _assert_target_codex_session(home, old_codex_session)


def test_clone_resume_command_selects_matching_agent_session(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    _write_codex_session(home, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    _write_claude_session(home, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    _write_cursor_store(home)
    _write_antigravity_transcript(home, "old-antigravity-session")
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    assert clone_resume_command("codex", result) == result.resume_commands["codex"]
    assert clone_resume_command("claude", result) == result.resume_commands["claude"]
    assert clone_resume_command("agent", result) == result.resume_commands["cursor"]
    assert clone_resume_command("agy-p", result) == result.resume_commands["antigravity"]
    assert clone_resume_command("/bin/bash", result) is None


def test_clone_window_agent_homes_does_not_resume_codex_without_session(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    root = home / ".web-terminal-acp" / "codex-homes" / str(SOURCE_WINDOW_ID)
    root.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    assert result.cloned_agents == ("codex",)
    assert result.session_ids == {"codex": ""}
    assert result.resume_commands == {}
    assert clone_resume_command("codex", result) is None


def test_clone_window_agent_homes_resumes_latest_codex_sqlite_thread(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    thread_id = "019e8838-38bb-7f41-98ec-e9460648e3a6"
    _write_codex_state_thread(home, thread_id)
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID)

    assert result.session_ids["codex"] == thread_id
    assert result.resume_commands["codex"].endswith(f"resume {thread_id}")


def test_clone_window_agent_homes_reuses_codex_thread_for_ephemeral_cache_hits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    old_thread_id = "019e8838-38bb-7f41-98ec-e9460648e3a6"
    _write_codex_state_thread(home, old_thread_id)
    _write_codex_session(home, old_thread_id)
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID, isolate_sessions=True)

    assert result.session_ids["codex"] == old_thread_id
    assert result.resume_commands["codex"].endswith(f"resume {old_thread_id}")
    target_state = (
        home / ".web-terminal-acp" / "codex-homes" / str(TARGET_WINDOW_ID) / "state_5.sqlite"
    )
    conn = sqlite3.connect(target_state)
    try:
        rows = conn.execute("select id, rollout_path from threads order by id").fetchall()
    finally:
        conn.close()
    target_session = (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(TARGET_WINDOW_ID)
        / "sessions"
        / "2026"
        / "06"
        / "02"
        / f"rollout-2026-06-02T00-00-00-{old_thread_id}.jsonl"
    )
    assert rows == [
        (
            old_thread_id,
            str(target_session),
        )
    ]
    assert _target_codex_session_files(home) == [target_session.name]


def test_clone_window_agent_homes_preserves_all_codex_threads_for_ephemeral_clone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    old_thread_id = "019e8838-38bb-7f41-98ec-e9460648e3a6"
    latest_thread_id = "019e8838-38bb-7f41-98ec-e9460648e3a7"
    _write_codex_state_thread(home, old_thread_id, updated_at=1780405780)
    _write_codex_state_thread(home, latest_thread_id, updated_at=1780405790, append=True)
    _write_codex_session(home, old_thread_id)
    _write_codex_session(home, latest_thread_id)
    monkeypatch.setattr(Path, "home", lambda: home)

    result = clone_window_agent_homes(SOURCE_WINDOW_ID, TARGET_WINDOW_ID, isolate_sessions=True)

    assert result.session_ids["codex"] == latest_thread_id
    target_state = (
        home / ".web-terminal-acp" / "codex-homes" / str(TARGET_WINDOW_ID) / "state_5.sqlite"
    )
    conn = sqlite3.connect(target_state)
    try:
        rows = conn.execute("select id from threads order by id").fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {old_thread_id, latest_thread_id}
    assert _target_codex_session_files(home) == [
        f"rollout-2026-06-02T00-00-00-{old_thread_id}.jsonl",
        f"rollout-2026-06-02T00-00-00-{latest_thread_id}.jsonl",
    ]


def test_remove_window_agent_homes_deletes_managed_root_and_alias(tmp_path: Path) -> None:
    home = tmp_path / "home"
    managed = home / ".web-terminal-acp" / "codex-homes" / str(TARGET_WINDOW_ID)
    alias = home / ".web-terminal-acp" / "codex-homes" / ".managed-home" / str(TARGET_WINDOW_ID)
    managed.mkdir(parents=True)
    alias.mkdir(parents=True)

    remove_window_agent_homes(TARGET_WINDOW_ID, home=home)

    assert not managed.exists()
    assert not alias.exists()


def _write_codex_session(home: Path, session_id: str) -> None:
    path = _codex_session_path(home, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": session_id}}) + "\n",
        encoding="utf-8",
    )


def _codex_session_path(home: Path, session_id: str) -> Path:
    return (
        home
        / ".web-terminal-acp"
        / "codex-homes"
        / str(SOURCE_WINDOW_ID)
        / "sessions"
        / "2026"
        / "06"
        / "02"
        / f"rollout-2026-06-02T00-00-00-{session_id}.jsonl"
    )


def _write_codex_state_thread(
    home: Path,
    thread_id: str,
    *,
    updated_at: int = 1780405780,
    append: bool = False,
) -> None:
    path = home / ".web-terminal-acp" / "codex-homes" / str(SOURCE_WINDOW_ID) / "state_5.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    if not append:
        conn.execute(
            "create table threads ("
            "id TEXT PRIMARY KEY, "
            "rollout_path TEXT NOT NULL DEFAULT '', "
            "updated_at INTEGER NOT NULL, "
            "archived INTEGER NOT NULL DEFAULT 0"
            ")"
        )
    conn.execute(
        "insert into threads (id, rollout_path, updated_at, archived) values (?, ?, ?, 0)",
        (thread_id, str(_codex_session_path(home, thread_id)), updated_at),
    )
    conn.commit()
    conn.close()


def _write_claude_session(home: Path, session_id: str) -> None:
    root = home / ".web-terminal-acp" / "claude-code-homes" / str(SOURCE_WINDOW_ID)
    transcript = root / "projects" / "-workspace-project" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"type": "assistant", "sessionId": session_id, "message": {"content": "hi"}})
        + "\n",
        encoding="utf-8",
    )
    (root / "history.jsonl").write_text(
        json.dumps({"display": "resume", "sessionId": session_id}) + "\n",
        encoding="utf-8",
    )


def _write_cursor_store(home: Path) -> None:
    path = (
        home / ".web-terminal-acp" / "cursor-homes" / str(SOURCE_WINDOW_ID) / "state" / "store.db"
    )
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(path)
    conn.execute("create table meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("create table blobs (id TEXT PRIMARY KEY, data BLOB)")
    meta = {
        "agentId": "cursor-agent-1",
        "latestRootBlobId": "root-1",
        "name": "Cursor Test Chat",
    }
    conn.execute(
        "insert into meta (key, value) values (?, ?)", ("0", json.dumps(meta).encode("utf-8").hex())
    )
    conn.execute(
        "insert into blobs (id, data) values (?, ?)",
        ("user-blob", json.dumps({"role": "user", "content": "hi"}).encode("utf-8")),
    )
    conn.commit()
    conn.close()


def _write_antigravity_transcript(home: Path, session_id: str) -> None:
    path = (
        home
        / ".web-terminal-acp"
        / "antigravity-cli-homes"
        / str(SOURCE_WINDOW_ID)
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "type": "USER",
                "content": "hi",
                "session_id": session_id,
                "conversationId": session_id,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _assert_target_codex_session(home: Path, session_id: str) -> None:
    target_files = _target_codex_session_paths(home)
    assert len(target_files) == 1
    assert session_id in target_files[0].name
    payload = json.loads(target_files[0].read_text(encoding="utf-8"))
    assert payload["payload"]["id"] == session_id


def _target_codex_session_paths(home: Path) -> list[Path]:
    return sorted((_target_codex_home(home) / "sessions").rglob("*.jsonl"))


def _target_codex_session_files(home: Path) -> list[str]:
    return [path.name for path in _target_codex_session_paths(home)]


def _target_codex_home(home: Path) -> Path:
    return home / ".web-terminal-acp" / "codex-homes" / str(TARGET_WINDOW_ID)


def _assert_claude_session_rewritten(home: Path, old_session_id: str, new_session_id: str) -> None:
    root = home / ".web-terminal-acp" / "claude-code-homes" / str(TARGET_WINDOW_ID)
    transcript = root / "projects" / "-workspace-project" / f"{new_session_id}.jsonl"
    assert transcript.is_file()
    assert not (root / "projects" / "-workspace-project" / f"{old_session_id}.jsonl").exists()
    assert json.loads(transcript.read_text(encoding="utf-8"))["sessionId"] == new_session_id
    assert (
        json.loads((root / "history.jsonl").read_text(encoding="utf-8"))["sessionId"]
        == new_session_id
    )


def _assert_cursor_store_rewritten(home: Path, new_session_id: str) -> None:
    store = (
        home / ".web-terminal-acp" / "cursor-homes" / str(TARGET_WINDOW_ID) / "state" / "store.db"
    )
    conn = sqlite3.connect(store)
    try:
        meta_hex = conn.execute("select value from meta where key = '0'").fetchone()[0]
        meta = json.loads(bytes.fromhex(meta_hex).decode("utf-8"))
        blob_id, raw_blob = conn.execute(
            "select id, data from blobs where id like ?", (f"{new_session_id}:%",)
        ).fetchone()
    finally:
        conn.close()
    assert meta["agentId"] == new_session_id
    assert meta["latestRootBlobId"].startswith(f"{new_session_id}:")
    assert blob_id.startswith(f"{new_session_id}:")
    assert json.loads(raw_blob.decode("utf-8"))["agentId"] == new_session_id


def _assert_antigravity_transcript_preserved(home: Path, session_id: str) -> None:
    transcript = (
        home
        / ".web-terminal-acp"
        / "antigravity-cli-homes"
        / str(TARGET_WINDOW_ID)
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    assert transcript.is_file()
    payload = json.loads(transcript.read_text(encoding="utf-8"))
    assert payload["session_id"] == session_id
