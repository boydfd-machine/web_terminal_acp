# ruff: noqa: F403,F405
from tests.unit.test_models_support import *

import importlib

from app.contexts.workspace.domain.project_todo_type_defaults import (
    BUILTIN_PROJECT_TODO_TYPE_DEFAULTS,
)

def test_alembic_revision_graph_has_unique_single_head():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)
    revisions = [revision.revision for revision in script.walk_revisions()]

    assert len(revisions) == len(set(revisions))
    assert script.get_heads() == ["20260629_0071"]

def test_project_todo_type_seed_migration_matches_builtin_defaults():
    migrations = [
        importlib.import_module("migrations.versions.20260607_0053_seed_project_todo_type_defaults"),
        importlib.import_module("migrations.versions.20260607_0057_seed_requirement_review_todo_type"),
    ]

    expected = {
        item.id: {
            "record_id": item.record_id,
            "id": item.id,
            "scope": "system",
            "name": item.name,
            "description": item.description,
            "agent": item.agent,
            "agent_profile_id": item.agent_profile_id,
            "artifact_kinds_json": list(item.artifact_kinds),
            "dispatch_template": item.dispatch_template,
        }
        for item in BUILTIN_PROJECT_TODO_TYPE_DEFAULTS
    }
    actual = {row["id"]: row for migration in migrations for row in migration._seed_rows()}

    assert expected == {}
    assert set(actual) == {
        "quick-fix",
        "ui-change",
        "debug",
        "small-feature",
        "large-feature",
        "solution-research",
        "performance-optimization",
        "review",
        "product-design",
        "user-review",
        "requirement-review",
    }

def test_sqlite_alembic_upgrade_from_ambiguous_0028_creates_terminal_notifications(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "ambiguous-0028.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    try:
        get_settings.cache_clear()
        command.upgrade(config, "20260530_0027")
        command.stamp(config, "20260531_0028")
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "terminal_notification_states" in tables


def test_migration_0067_tolerates_pre_existing_owner_user_id_column(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "drift-0067.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    try:
        get_settings.cache_clear()
        command.upgrade(config, "20260612_0066")
        drift_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
        with drift_engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE project_todo_types ADD COLUMN owner_user_id VARCHAR(255)"
            )
        drift_engine.dispose()
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    verify_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with verify_engine.connect() as connection:
            index_rows = connection.exec_driver_sql(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = 'project_todo_types'"
            )
            indexes = {row[0] for row in index_rows}
    finally:
        verify_engine.dispose()

    assert "uq_project_todo_types_global_system_id" in indexes
    assert "uq_project_todo_types_user_system_id" in indexes
    assert "uq_project_todo_types_system_id" not in indexes

def test_folder_has_materialized_path():
    folder = Folder(name="生产排障", path="/2026-05/生产排障")
    assert folder.name == "生产排障"
    assert folder.path == "/2026-05/生产排障"

def test_client_status_and_runtime_values_are_stable():
    assert ClientStatus.ONLINE.value == "ONLINE"
    assert ClientStatus.OFFLINE.value == "OFFLINE"
    assert ClientStatus.ERROR.value == "ERROR"
    assert ClientRuntime.local.value == "local"
    assert ClientRuntime.remote.value == "remote"

def test_window_status_values_are_stable():
    assert WindowStatus.active.value == "ACTIVE"
    assert WindowStatus.archived.value == "ARCHIVED"
    assert WindowStatus.error.value == "ERROR"
    assert WindowStatus.disconnected.value == "DISCONNECTED"

def test_event_source_type_values_are_stable():
    assert EventSourceType.terminal.value == "terminal"
    assert EventSourceType.claude_jsonl.value == "claude_jsonl"
    assert EventSourceType.codex_trace.value == "codex_trace"
    assert EventSourceType.summary.value == "summary"
    assert EventSourceType.agent_tool_record.value == "agent_tool_record"

def test_virtual_window_references_folder_id():
    window = VirtualWindow(title="Terminal-15:30", folder_id=None)
    assert window.folder_id is None

def test_model_enum_columns_persist_values():
    client_status_values = Client.__table__.c.status.type.enums
    assert client_status_values == ["ONLINE", "OFFLINE", "ERROR"]

    client_runtime_values = Client.__table__.c.runtime.type.enums
    assert client_runtime_values == ["local", "remote"]

    window_values = VirtualWindow.__table__.c.status.type.enums
    assert window_values == ["ACTIVE", "ARCHIVED", "ERROR", "DISCONNECTED"]

    event_source_values = Event.__table__.c.source_type.type.enums
    assert event_source_values == [
        "terminal",
        "claude_jsonl",
        "codex_trace",
        "summary",
        "agent_tool_record",
    ]

    summary_job_status_values = SummaryJob.__table__.c.status.type.enums
    assert summary_job_status_values == ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]

def test_metadata_schema_constraints_match_spec():
    folder_constraints = {
        tuple(constraint.columns.keys())
        for constraint in Folder.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("client_id", "path") in folder_constraints
    assert ("client_id", "parent_id", "name") in folder_constraints

    event_constraints = {
        tuple(constraint.columns.keys())
        for constraint in Event.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("client_id", "fingerprint") in event_constraints
    assert ("fingerprint",) not in event_constraints

    expected_indexes = {
        ("clients", ("status",)),
        ("clients", ("runtime",)),
        ("clients", ("owner_user_id",)),
        ("users", ("auth_provider", "subject")),
        ("folders", ("client_id",)),
        ("folders", ("parent_id",)),
        ("virtual_windows", ("client_id",)),
        ("virtual_windows", ("folder_id",)),
        ("virtual_windows", ("status",)),
        ("ai_sessions", ("client_id",)),
        ("ai_sessions", ("virtual_window_id",)),
        ("events", ("client_id",)),
        ("events", ("virtual_window_id",)),
        ("events", ("ai_session_id",)),
        ("events", ("source_type", "source_id")),
        ("events", ("source_type", "created_at", "id")),
        ("events", ("client_id", "virtual_window_id", "source_type", "created_at", "id")),
        ("events", ("client_id", "virtual_window_id", "kind", "created_at", "id")),
        ("events", ("client_id", "virtual_window_id", "created_at", "id")),
        ("events", ("client_id", "created_at", "id")),
        ("summary_jobs", ("virtual_window_id",)),
        ("summary_jobs", ("status", "run_after")),
        ("project_todos", ("parent_todo_id",)),
        ("project_todos", ("client_id", "project_path", "updated_at", "id")),
        ("project_todos", ("client_id", "project_path", "sort_order", "updated_at", "id")),
        ("project_todos", ("updated_at", "id", "client_id", "assigned_window_id")),
        ("project_todo_types", ("id",)),
        ("project_todo_types", ("owner_user_id", "id")),
        ("project_agent_preferences", ("client_id", "project_path")),
        ("project_todo_work_snapshots", ("project_todo_id", "captured_at", "id")),
        ("project_todo_review_targets", ("project_todo_id", "updated_at", "id")),
        ("project_todo_review_runs", ("project_todo_id", "created_at", "id")),
        ("project_todo_artifacts", ("review_run_id",)),
        ("project_todo_artifacts", ("created_by_window_id",)),
        ("project_todo_attachments", ("project_todo_id", "created_at", "id")),
        ("project_todo_attachments", ("client_id", "project_path", "created_at")),
        ("project_todo_attachments", ("status", "updated_at")),
        ("window_title_history", ("client_id", "virtual_window_id", "created_at", "id")),
    }
    actual_indexes = {
        (table.name, tuple(index.columns.keys()))
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert expected_indexes <= actual_indexes
    summary_active_index = next(
        index
        for index in SummaryJob.__table__.indexes
        if index.name == "uq_summary_jobs_active_virtual_window_id"
    )
    assert summary_active_index.unique is True
    assert tuple(summary_active_index.columns.keys()) == ("virtual_window_id",)
    assert summary_active_index.dialect_options["postgresql"]["where"].right.value is SummaryJobStatus.pending
    assert summary_active_index.dialect_options["sqlite"]["where"].right.value is SummaryJobStatus.pending

    agent_activity_index = next(
        index
        for index in Event.__table__.indexes
        if index.name == "ix_events_agent_activity_window_created"
    )
    assert tuple(agent_activity_index.columns.keys()) == (
        "client_id",
        "virtual_window_id",
        "created_at",
        "id",
    )
    assert agent_activity_index.dialect_options["postgresql"]["where"] is not None
    assert agent_activity_index.dialect_options["sqlite"]["where"] is not None

    terminal_input_index = next(
        index
        for index in Event.__table__.indexes
        if index.name == "ix_events_terminal_input_window_created"
    )
    terminal_finished_index = next(
        index
        for index in Event.__table__.indexes
        if index.name == "ix_events_terminal_finished_window_created"
    )
    assert tuple(terminal_input_index.columns.keys()) == (
        "client_id",
        "virtual_window_id",
        "created_at",
        "id",
    )
    assert tuple(terminal_finished_index.columns.keys()) == (
        "client_id",
        "virtual_window_id",
        "created_at",
        "id",
    )
    assert terminal_input_index.dialect_options["postgresql"]["where"] is not None
    assert terminal_input_index.dialect_options["sqlite"]["where"] is not None
    assert terminal_finished_index.dialect_options["postgresql"]["where"] is not None
    assert terminal_finished_index.dialect_options["sqlite"]["where"] is not None

    worktree_attention_index = next(
        index
        for index in ProjectTodo.__table__.indexes
        if index.name == "ix_project_todos_worktree_attention"
    )
    assert tuple(worktree_attention_index.columns.keys()) == (
        "updated_at",
        "id",
        "client_id",
        "assigned_window_id",
    )
    assert worktree_attention_index.dialect_options["postgresql"]["where"] is not None
    assert worktree_attention_index.dialect_options["sqlite"]["where"] is not None

    assert Client.__table__.c.status.server_default is not None
    assert Client.__table__.c.runtime.server_default is not None
    assert Folder.__table__.c.client_id.nullable is False
    assert VirtualWindow.__table__.c.client_id.nullable is False
    assert VirtualWindow.__table__.c.remote_session_id.nullable is True
    assert VirtualWindow.__table__.c.remote_window_id.nullable is True
    assert VirtualWindow.__table__.c.title_manually_overridden.nullable is False
    assert VirtualWindow.__table__.c.folder_manually_overridden.nullable is False
    assert VirtualWindow.__table__.c.agent_activity_latest_at.nullable is True
    assert VirtualWindow.__table__.c.agent_presence_latest_at.nullable is True
    assert VirtualWindow.__table__.c.agent_activity_latest_event_id.nullable is True
    assert VirtualWindow.__table__.c.agent_activity_latest_completed_at.nullable is True
    assert VirtualWindow.__table__.c.agent_activity_latest_user_input_at.nullable is True
    assert VirtualWindow.__table__.c.agent_activity_burst_start_at.nullable is True
    assert VirtualWindow.__table__.c.agent_activity_generation.nullable is False
    assert VirtualWindow.__table__.c.manual_work_status_state.nullable is True
    assert VirtualWindow.__table__.c.manual_work_status_updated_at.nullable is True
    assert AiSession.__table__.c.client_id.nullable is False
    assert Event.__table__.c.client_id.nullable is False
    assert ProjectTodo.__table__.c.parent_todo_id.nullable is True
    assert Base.metadata.tables["ui_settings"].c.value_json.nullable is False

    assert Folder.__table__.c.sort_order.server_default is not None
    assert VirtualWindow.__table__.c.status.server_default is not None
    assert VirtualWindow.__table__.c.title_manually_overridden.server_default is not None
    assert VirtualWindow.__table__.c.folder_manually_overridden.server_default is not None
    assert VirtualWindow.__table__.c.agent_activity_generation.server_default is not None
    assert SummaryJob.__table__.c.status.server_default is not None
    assert SummaryJob.__table__.c.attempts.server_default is not None
    assert SummaryJob.__table__.c.allow_title_folder_override.nullable is False
    assert SummaryJob.__table__.c.allow_title_folder_override.server_default is not None
    assert SummaryJob.__table__.c.input_generation.nullable is False
    assert SummaryJob.__table__.c.input_generation.server_default is not None

    assert Event.__table__.c.payload_json.nullable is False
    assert Event.__table__.c.indexed_at.nullable is True
    assert Event.__table__.c.indexed_at.server_default is None
    attachments_table = Base.metadata.tables["project_todo_attachments"]
    assert attachments_table.c.client_id.nullable is False
    assert attachments_table.c.project_path.nullable is False
    assert attachments_table.c.object_key.nullable is False
    assert attachments_table.c.filename.nullable is False
    assert attachments_table.c.content_type.nullable is False
    assert attachments_table.c.status.server_default is not None
    project_todo_types_table = Base.metadata.tables["project_todo_types"]
    assert project_todo_types_table.c.owner_user_id.nullable is True

    assert SummaryJob.__table__.c.trigger_reason.nullable is True
    assert SummaryJob.__table__.c.run_after.nullable is True
    assert SummaryJob.__table__.c.run_after.server_default is None
    assert WindowTitleHistory.__table__.c.client_id.nullable is False
    assert WindowTitleHistory.__table__.c.virtual_window_id.nullable is False
    assert WindowTitleHistory.__table__.c.title.nullable is False
    assert WindowTitleHistory.__table__.c.summary.nullable is True
    assert WindowTitleHistory.__table__.c.source.nullable is False

def test_sqlite_create_all_persists_models_and_relationships():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        client = Client(
            id=LOCAL_CLIENT_ID,
            name="local",
            status=ClientStatus.ONLINE,
            token_hash=f"sha256:{'0' * 64}",
            runtime=ClientRuntime.local,
        )
        folder = Folder(name="生产排障", path="/2026-05/生产排障", client=client)
        window = VirtualWindow(
            title="Terminal-15:30",
            client=client,
            folder=folder,
            status=WindowStatus.archived,
            title_tags=["prod", "incident"],
        )
        ai_session = AiSession(
            provider="claude",
            source_id="session-1",
            client=client,
            virtual_window=window,
            tags=["triage"],
        )
        event = Event(
            source_type=EventSourceType.terminal,
            source_id="pane-1",
            kind="output",
            client=client,
            virtual_window=window,
            ai_session=ai_session,
            payload_json={"line": "ok", "nested": {"count": 1}},
            fingerprint="event-1",
        )
        job = SummaryJob(
            virtual_window=window,
            status=SummaryJobStatus.pending,
        )
        title_history = WindowTitleHistory(
            client=client,
            virtual_window=window,
            title="Terminal-15:30",
            summary="Initial summary.",
            source="summary",
        )
        session.add_all([folder, window, ai_session, event, job, title_history])
        session.commit()

        assert client.id == LOCAL_CLIENT_ID
        assert folder.id is not None
        assert folder.client_id == client.id
        assert window.id is not None
        assert window.client_id == client.id
        assert ai_session.id is not None
        assert ai_session.client_id == client.id
        assert event.id is not None
        assert event.client_id == client.id
        assert job.id is not None

    with Session(engine) as session:
        loaded_window = session.scalars(
            select(VirtualWindow).where(VirtualWindow.title == "Terminal-15:30")
        ).one()
        assert loaded_window.status is WindowStatus.archived
        assert loaded_window.title_tags == ["prod", "incident"]
        assert loaded_window.title_manually_overridden is False
        assert loaded_window.folder_manually_overridden is False
        assert loaded_window.client is not None
        assert loaded_window.client.name == "local"
        assert loaded_window.folder is not None
        assert loaded_window.folder.name == "生产排障"

        loaded_event = session.scalars(select(Event).where(Event.fingerprint == "event-1")).one()
        assert loaded_event.source_type is EventSourceType.terminal
        assert loaded_event.payload_json == {"line": "ok", "nested": {"count": 1}}
        assert loaded_event.ai_session is not None
        assert loaded_event.ai_session.provider == "claude"

        loaded_job = session.scalars(
            select(SummaryJob).where(SummaryJob.virtual_window_id == loaded_window.id)
        ).one()
        assert loaded_job.status is SummaryJobStatus.pending
        assert loaded_job.trigger_reason is None
        assert loaded_job.allow_title_folder_override is False
        assert loaded_job.input_generation == 0
        assert loaded_job.virtual_window.title == "Terminal-15:30"
        loaded_title_history = session.scalars(
            select(WindowTitleHistory).where(WindowTitleHistory.virtual_window_id == loaded_window.id)
        ).one()
        assert loaded_title_history.client_id == loaded_window.client_id
        assert loaded_title_history.title == "Terminal-15:30"
        assert loaded_title_history.summary == "Initial summary."
        assert loaded_title_history.source == "summary"

def test_sqlite_folder_sibling_unique_constraint_rejects_duplicate_names():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        parent = Folder(name="root", path="/root")
        session.add(parent)
        session.flush()

        session.add_all(
            [
                Folder(name="duplicate", path="/root/one", parent_id=parent.id),
                Folder(name="duplicate", path="/root/two", parent_id=parent.id),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()

def test_sqlite_create_all_scopes_event_fingerprints_by_client():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    _assert_event_fingerprint_scoped_by_client(engine)

def test_sqlite_create_all_rejects_invalid_metadata_enum_values():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    _assert_invalid_metadata_values_rejected(engine)

def test_sqlite_create_all_accepts_arbitrary_ai_session_providers():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    _assert_arbitrary_providers_accepted(engine)

def test_initial_postgresql_local_client_seed_casts_uuid():
    statement = initial_migration._seed_local_client_statement(is_postgresql=True)

    sql = str(statement)
    assert f"'{LOCAL_CLIENT_ID}'::uuid" in sql
    assert "'ONLINE'::clientstatus" in sql
    assert "'local'::clientruntime" in sql
    assert statement.compile().params == {
        "token_hash": initial_migration.LOCAL_CLIENT_UNUSABLE_TOKEN_HASH
    }

def test_sqlite_alembic_migration_adds_terminal_summary_control_defaults(tmp_path, monkeypatch):
    database_path = tmp_path / "migrated-summary-controls.db"
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
    job_id = _uuid_hex()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        _insert_valid_window(connection, window_id)
        connection.exec_driver_sql(
            "INSERT INTO summary_jobs (id, virtual_window_id) VALUES (?, ?)",
            (job_id, window_id),
        )
        window_row = connection.exec_driver_sql(
            "SELECT title_manually_overridden, folder_manually_overridden "
            "FROM virtual_windows WHERE id = ?",
            (window_id,),
        ).mappings().one()
        job_row = connection.exec_driver_sql(
            "SELECT trigger_reason, allow_title_folder_override, input_generation "
            "FROM summary_jobs WHERE id = ?",
            (job_id,),
        ).mappings().one()

    assert window_row["title_manually_overridden"] == 0
    assert window_row["folder_manually_overridden"] == 0
    assert job_row["trigger_reason"] is None
    assert job_row["allow_title_folder_override"] == 0
    assert job_row["input_generation"] == 0
