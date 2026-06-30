from tests.unit.test_models_support import *

import json

def test_sqlite_alembic_migration_seeds_local_client_parent_row(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-local-client.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        row = connection.exec_driver_sql(
            "SELECT id, name, status, runtime, token_hash FROM clients WHERE id = ?",
            (LOCAL_CLIENT_ID.hex,),
        ).mappings().one()
        assert row["name"] == "local"
        assert row["status"] == ClientStatus.ONLINE.value
        assert row["runtime"] == ClientRuntime.local.value
        assert row["token_hash"].startswith("sha256:")
        assert row["token_hash"] != hash_client_token("local-client-token")

        connection.exec_driver_sql(
            "INSERT INTO folders (id, name, path) VALUES (?, ?, ?)",
            (_uuid_hex(), "default-client-folder", "/default-client-folder"),
        )

    with Session(engine) as session:
        assert session.get(Client, LOCAL_CLIENT_ID) is not None
        assert session.scalars(select(Client).where(Client.runtime == ClientRuntime.local)).all() == [
            session.get(Client, LOCAL_CLIENT_ID)
        ]

def test_sqlite_alembic_migration_seeds_builtin_project_todo_types(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-project-todo-types.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        rows = connection.exec_driver_sql(
            "SELECT id, name, agent, agent_profile_id, artifact_kinds_json, "
            "input_artifact_ids_json, dispatch_template "
            "FROM project_todo_types "
            "WHERE scope = 'system' "
            "ORDER BY id"
        ).mappings().all()

    assert rows == []

def test_sqlite_alembic_migration_repairs_legacy_project_todo_0058_state(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-project-todo-0058.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    def run_alembic(action: str, revision: str) -> None:
        get_settings.cache_clear()
        try:
            getattr(command, action)(config, revision)
        finally:
            get_settings.cache_clear()

    run_alembic("upgrade", "20260607_0057")
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE INDEX ix_project_todos_client_project_updated "
            "ON project_todos (client_id, project_path, updated_at, id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_project_todos_artifact_candidates "
            "ON project_todos (client_id, project_path, sort_order, updated_at, id) "
            "WHERE artifact_kinds_json IS NOT NULL "
            "AND assigned_window_id IS NOT NULL "
            "AND status IN ('AWAITING_REVIEW', 'DONE')"
        )
    engine.dispose()
    run_alembic("stamp", "20260608_0058")

    run_alembic("upgrade", "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.connect() as connection:
        columns = {
            row["name"]
            for row in connection.exec_driver_sql("PRAGMA table_info(project_todos)").mappings()
        }
        indexes = {
            row["name"]
            for row in connection.exec_driver_sql("PRAGMA index_list(project_todos)").mappings()
        }
    assert "dispatch_output_language" in columns
    assert "ix_project_todos_client_project_updated" in indexes
    assert "ix_project_todos_artifact_candidates" in indexes

def test_sqlite_alembic_migration_repairs_legacy_project_todo_0059_missing_column(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "legacy-project-todo-0059.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    def run_alembic(action: str, revision: str) -> None:
        get_settings.cache_clear()
        try:
            getattr(command, action)(config, revision)
        finally:
            get_settings.cache_clear()

    run_alembic("upgrade", "20260607_0057")
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE INDEX ix_project_todos_client_project_updated "
            "ON project_todos (client_id, project_path, updated_at, id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_project_todos_artifact_candidates "
            "ON project_todos (client_id, project_path, sort_order, updated_at, id) "
            "WHERE artifact_kinds_json IS NOT NULL "
            "AND assigned_window_id IS NOT NULL "
            "AND status IN ('AWAITING_REVIEW', 'DONE')"
        )
    engine.dispose()
    run_alembic("stamp", "20260608_0059")

    run_alembic("upgrade", "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.connect() as connection:
        columns = {
            row["name"]
            for row in connection.exec_driver_sql("PRAGMA table_info(project_todos)").mappings()
        }
    assert "dispatch_output_language" in columns

def test_sqlite_alembic_migrated_schema_creates_ui_settings(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-ui-settings.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO ui_settings (key, value_json) VALUES (?, ?)",
            ("custom_quick_keys", '{"quick_keys": []}'),
        )
        row = connection.exec_driver_sql(
            "SELECT value_json FROM ui_settings WHERE key = ?",
            ("custom_quick_keys",),
        ).mappings().one()

    assert row["value_json"] == '{"quick_keys": []}'

def test_sqlite_alembic_migrated_schema_creates_window_title_history(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-title-history.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    window_id = _uuid_hex()
    history_id = _uuid_hex()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        _insert_valid_window(connection, window_id)
        connection.exec_driver_sql(
            "INSERT INTO window_title_history "
            "(id, client_id, virtual_window_id, title, summary, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                history_id,
                LOCAL_CLIENT_ID.hex,
                window_id,
                "Terminal-15:30",
                "Initial summary.",
                "summary",
            ),
        )
        row = connection.exec_driver_sql(
            "SELECT title, summary, source FROM window_title_history WHERE id = ?",
            (history_id,),
        ).mappings().one()

    assert row["title"] == "Terminal-15:30"
    assert row["summary"] == "Initial summary."
    assert row["source"] == "summary"

def test_sqlite_alembic_migrated_schema_scopes_event_fingerprints_by_client(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-event-fingerprint.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    _assert_event_fingerprint_scoped_by_client(engine)

def test_sqlite_alembic_migrated_schema_rejects_invalid_metadata_enum_values(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "migrated.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    _assert_invalid_metadata_values_rejected(engine)

def test_sqlite_alembic_migrated_schema_accepts_arbitrary_ai_session_providers(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "migrated.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    _assert_arbitrary_providers_accepted(engine)

def test_sqlite_alembic_agent_tool_record_downgrade_removes_rows_and_reupgrades(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "agent-tool-record-downgrade.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    def run_alembic(action: str, revision: str) -> None:
        get_settings.cache_clear()
        try:
            getattr(command, action)(config, revision)
        finally:
            get_settings.cache_clear()

    run_alembic("upgrade", "head")

    legacy_session_id = _uuid_hex()
    non_legacy_session_id = _uuid_hex()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO ai_sessions (id, provider, source_id) VALUES (?, ?, ?)",
            (legacy_session_id, "claude", "legacy-session"),
        )
        connection.exec_driver_sql(
            "INSERT INTO ai_sessions (id, provider, source_id) VALUES (?, ?, ?)",
            (non_legacy_session_id, "cursor_cli", "generic-session"),
        )
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, source_type, source_id, kind, ai_session_id, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _uuid_hex(),
                "agent_tool_record",
                "session-1",
                "message",
                legacy_session_id,
                "{}",
                "agent-event-1",
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, source_type, source_id, kind, ai_session_id, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _uuid_hex(),
                "codex_trace",
                "legacy-linked",
                "message",
                legacy_session_id,
                "{}",
                "legacy-event-1",
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, source_type, source_id, kind, ai_session_id, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _uuid_hex(),
                "codex_trace",
                "generic-linked",
                "message",
                non_legacy_session_id,
                "{}",
                "generic-linked-event-1",
            ),
        )
    engine.dispose()

    run_alembic("downgrade", "20260523_0008")

    downgraded_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with downgraded_engine.connect() as connection:
        agent_rows = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM events WHERE source_type = 'agent_tool_record'"
        ).scalar_one()
        non_legacy_sessions = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM ai_sessions WHERE provider NOT IN ('claude', 'codex')"
        ).scalar_one()
        legacy_event_ai_session_id = connection.exec_driver_sql(
            "SELECT ai_session_id FROM events WHERE fingerprint = 'legacy-event-1'"
        ).scalar_one()
        generic_linked_event_ai_session_id = connection.exec_driver_sql(
            "SELECT ai_session_id FROM events WHERE fingerprint = 'generic-linked-event-1'"
        ).scalar_one()
    assert agent_rows == 0
    assert non_legacy_sessions == 0
    assert legacy_event_ai_session_id == legacy_session_id
    assert generic_linked_event_ai_session_id is None

    with pytest.raises(IntegrityError):
        with downgraded_engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO events "
                "(id, source_type, source_id, kind, payload_json, fingerprint) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_uuid_hex(), "agent_tool_record", "session-2", "message", "{}", "agent-event-2"),
            )
    downgraded_engine.dispose()

    run_alembic("upgrade", "head")

    reupgraded_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with reupgraded_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, source_type, source_id, kind, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid_hex(), "agent_tool_record", "session-3", "message", "{}", "agent-event-3"),
        )
    reupgraded_engine.dispose()
