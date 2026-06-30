import importlib

import uuid

from pathlib import Path

import pytest

from alembic import command

from alembic.config import Config

from alembic.script import ScriptDirectory

from sqlalchemy import create_engine, select

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session

from app.config import get_settings

from app.model_base import Base

from app.models import (
    AiSession,
    Client,
    ClientRuntime,
    ClientStatus,
    Event,
    EventSourceType,
    Folder,
    LOCAL_CLIENT_ID,
    ProjectTodo,
    SummaryJob,
    SummaryJobStatus,
    VirtualWindow,
    WindowTitleHistory,
    WindowStatus,
)

from app.repositories.clients import hash_client_token

BACKEND_DIR = Path(__file__).resolve().parents[2]

initial_migration = importlib.import_module("migrations.versions.20260520_0001_initial")

def _uuid_hex() -> str:
    return uuid.uuid4().hex

def _insert_valid_window(connection, window_id: str) -> None:
    connection.exec_driver_sql(
        "INSERT INTO virtual_windows (id, title, status) VALUES (?, ?, ?)",
        (window_id, "Terminal-15:30", WindowStatus.active.value),
    )

def _insert_valid_ai_session(connection, provider: str) -> None:
    connection.exec_driver_sql(
        "INSERT INTO ai_sessions (id, provider, source_id) VALUES (?, ?, ?)",
        (_uuid_hex(), provider, f"{provider}-session"),
    )

def _assert_arbitrary_providers_accepted(engine) -> None:
    with engine.begin() as connection:
        _insert_valid_ai_session(connection, "claude")
        _insert_valid_ai_session(connection, "codex")
        _insert_valid_ai_session(connection, "cursor_cli")
        _insert_valid_ai_session(connection, "openai")

    with engine.connect() as connection:
        providers = connection.exec_driver_sql(
            "SELECT provider FROM ai_sessions ORDER BY provider"
        ).scalars()
        assert list(providers) == ["claude", "codex", "cursor_cli", "openai"]

def _assert_event_fingerprint_scoped_by_client(engine) -> None:
    first_client_id = _uuid_hex()
    second_client_id = _uuid_hex()
    fingerprint = "shared-fingerprint"

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO clients (id, name, status, token_hash, runtime) VALUES (?, ?, ?, ?, ?)",
            (first_client_id, "client-a", "ONLINE", f"sha256:{'1' * 64}", "remote"),
        )
        connection.exec_driver_sql(
            "INSERT INTO clients (id, name, status, token_hash, runtime) VALUES (?, ?, ?, ?, ?)",
            (second_client_id, "client-b", "ONLINE", f"sha256:{'2' * 64}", "remote"),
        )
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, client_id, source_type, source_id, kind, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_uuid_hex(), first_client_id, "terminal", "pane-1", "output", "{}", fingerprint),
        )
        connection.exec_driver_sql(
            "INSERT INTO events "
            "(id, client_id, source_type, source_id, kind, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_uuid_hex(), second_client_id, "terminal", "pane-1", "output", "{}", fingerprint),
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO events "
                "(id, client_id, source_type, source_id, kind, payload_json, fingerprint) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_uuid_hex(), first_client_id, "terminal", "pane-2", "output", "{}", fingerprint),
            )

def _assert_invalid_metadata_values_rejected(engine) -> None:
    window_id = _uuid_hex()
    with engine.begin() as connection:
        _insert_valid_window(connection, window_id)

    invalid_inserts = [
        (
            "INSERT INTO virtual_windows (id, title, status) VALUES (?, ?, ?)",
            (_uuid_hex(), "bad window", "BROKEN"),
        ),
        (
            "INSERT INTO events "
            "(id, source_type, source_id, kind, payload_json, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid_hex(), "bad_source", "source-1", "output", "{}", _uuid_hex()),
        ),
        (
            "INSERT INTO summary_jobs (id, virtual_window_id, status) VALUES (?, ?, ?)",
            (_uuid_hex(), window_id, "BROKEN"),
        ),
    ]

    for statement, parameters in invalid_inserts:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql(statement, parameters)

__all__ = [name for name in globals() if not name.startswith("__")]
