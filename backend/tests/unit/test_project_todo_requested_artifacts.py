from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.contexts.workspace.application.project_todo_requested_artifacts import (
    linked_requested_artifacts_for_todos,
)


@pytest.mark.asyncio
async def test_linked_requested_artifacts_query_omits_large_artifact_payload_columns() -> None:
    class CaptureSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return []

    session = CaptureSession()

    await linked_requested_artifacts_for_todos(
        session,
        [uuid4()],
        purpose="todo_artifact",
    )

    compiled = str(session.statement.compile(dialect=postgresql.dialect()))

    assert "terminal_artifacts.content_json" not in compiled
    assert "terminal_artifacts.display_html" not in compiled
    assert "terminal_artifacts.status" in compiled
    assert "terminal_artifacts.last_error" in compiled
