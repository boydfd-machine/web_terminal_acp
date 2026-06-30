import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import QueuePool

from app.config import Settings
from app.db import engine_create_kwargs, prefer_deferred_commit


class _FakeDialect:
    name = "postgresql"


class _FakeBind:
    dialect = _FakeDialect()


class _FakePostgresqlSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def get_bind(self) -> _FakeBind:
        return _FakeBind()

    async def execute(self, statement):  # noqa: ANN001
        self.statements.append(str(statement))


@pytest.mark.asyncio
async def test_prefer_deferred_commit_skips_non_postgresql() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def capture_statement(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    async with AsyncSession(engine) as session:
        await prefer_deferred_commit(session)

    await engine.dispose()

    assert statements == []


@pytest.mark.asyncio
async def test_prefer_deferred_commit_sets_postgresql_local_synchronous_commit() -> None:
    session = _FakePostgresqlSession()

    await prefer_deferred_commit(session)  # type: ignore[arg-type]

    assert session.statements == ["SET LOCAL synchronous_commit = OFF"]


def test_engine_create_kwargs_maps_settings_to_pool_options() -> None:
    settings = Settings(
        _env_file=None,
        db_pool_size=12,
        db_max_overflow=24,
        db_pool_pre_ping=False,
        db_pool_recycle_seconds=900,
    )

    assert engine_create_kwargs(settings) == {
        "pool_size": 12,
        "max_overflow": 24,
        "pool_pre_ping": False,
        "pool_recycle": 900,
    }


def test_engine_built_from_settings_uses_configured_queue_pool(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'engine.db'}",
        db_pool_size=7,
        db_max_overflow=13,
        db_pool_pre_ping=True,
        db_pool_recycle_seconds=300,
    )

    engine = create_async_engine(settings.database_url, future=True, **engine_create_kwargs(settings))
    try:
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 7
        assert engine.pool._max_overflow == 13
    finally:
        engine.sync_engine.dispose()
