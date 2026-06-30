import io
import zipfile

import pytest

from tests.integration.test_agent_profiles_api import DbClient
from tests.integration.test_agent_profiles_api import db_client  # noqa: F401


@pytest.mark.asyncio
async def test_system_agent_config_api_downloads_builtin_skill(
    db_client: DbClient,
) -> None:
    response = await db_client.get("/api/system-agent-config/skills/agent-trace-graph/download")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as downloaded:
        names = set(downloaded.namelist())
        assert {
            "agent-trace-graph/SKILL.md",
            "agent-trace-graph/scripts/render.py",
            "agent-trace-graph/agents/openai.yaml",
        } <= names
