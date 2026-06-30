import importlib


summary_pending_unique = importlib.import_module(
    "migrations.versions.20260604_0035_summary_pending_unique"
)


class _FakeDialect:
    def __init__(self, name: str):
        self.name = name


class _FakeBind:
    def __init__(self, dialect_name: str):
        self.dialect = _FakeDialect(dialect_name)


class _FakeAutocommitBlock:
    def __init__(self, operations):
        self._operations = operations

    def __enter__(self):
        self._operations.append(("autocommit_enter",))

    def __exit__(self, exc_type, exc, traceback):
        self._operations.append(("autocommit_exit",))


class _FakeContext:
    def __init__(self, operations):
        self._operations = operations

    def autocommit_block(self):
        return _FakeAutocommitBlock(self._operations)


class _FakeOp:
    def __init__(self, dialect_name: str):
        self.operations = []
        self._bind = _FakeBind(dialect_name)
        self._context = _FakeContext(self.operations)

    def get_bind(self):
        return self._bind

    def get_context(self):
        return self._context

    def execute(self, statement):
        self.operations.append(("execute", str(statement)))

    def drop_index(self, *args, **kwargs):
        self.operations.append(("drop_index", args, kwargs))

    def create_index(self, *args, **kwargs):
        self.operations.append(("create_index", args, kwargs))


def test_summary_pending_unique_upgrade_uses_concurrent_postgres_index_rebuild(monkeypatch):
    fake_op = _FakeOp("postgresql")
    monkeypatch.setattr(summary_pending_unique, "op", fake_op)

    summary_pending_unique.upgrade()

    assert [operation[0] for operation in fake_op.operations] == [
        "autocommit_enter",
        "execute",
        "execute",
        "autocommit_exit",
    ]
    statements = [operation[1] for operation in fake_op.operations if operation[0] == "execute"]
    assert statements == [
        "DROP INDEX CONCURRENTLY IF EXISTS uq_summary_jobs_active_virtual_window_id",
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
        "uq_summary_jobs_active_virtual_window_id "
        "ON summary_jobs (virtual_window_id) WHERE status = 'PENDING'",
    ]


def test_summary_pending_unique_downgrade_uses_concurrent_postgres_index_rebuild(monkeypatch):
    fake_op = _FakeOp("postgresql")
    monkeypatch.setattr(summary_pending_unique, "op", fake_op)

    summary_pending_unique.downgrade()

    assert [operation[0] for operation in fake_op.operations] == [
        "autocommit_enter",
        "execute",
        "execute",
        "autocommit_exit",
    ]
    statements = [operation[1] for operation in fake_op.operations if operation[0] == "execute"]
    assert statements == [
        "DROP INDEX CONCURRENTLY IF EXISTS uq_summary_jobs_active_virtual_window_id",
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
        "uq_summary_jobs_active_virtual_window_id "
        "ON summary_jobs (virtual_window_id) WHERE status IN ('PENDING', 'RUNNING')",
    ]
