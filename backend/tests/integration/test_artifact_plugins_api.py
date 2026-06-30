from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import Base, get_session
from app.main import app
from app.platform.plugins.artifact_plugins import (
    get_project_artifact_plugin_registry,
    get_terminal_artifact_plugin_registry,
    reset_artifact_plugin_registries,
)
from tests.integration.auth_api_support import (
    auth_db_client,  # noqa: F401 - imported to register the pytest fixture in this module.
    keycloak_token,
    public_key_pem,
)


PLUGIN_SOURCE = '''
from app.platform.plugins.artifact_plugins.types import TerminalArtifactRender


class DemoArtifactPlugin:
    artifact_kind = "demo_report"
    label = "Demo Report"
    default_title = "Demo report"

    def build_prompt(self, *, source_title, user_prompt=None, output_path=None):
        return f"Build demo report for {source_title}"

    def parse_output(self, output):
        return {"text": output}

    def render(self, content_json):
        return TerminalArtifactRender(
            content_json=content_json,
            display_html="<html><body>demo</body></html>",
            metadata_json={"renderer": "demo"},
        )


def create_plugin():
    return DemoArtifactPlugin()
'''.strip()


UPDATED_PLUGIN_SOURCE = PLUGIN_SOURCE.replace("Demo Report", "Updated Demo Report")
BROKEN_PLUGIN_SOURCE = "PLUGIN = object()\n"
TEMPLATE_PLUGIN_PAYLOAD = {
    "python_source": '''
ARTIFACT_KIND = "demo_template"
LABEL = "Demo Template"
DEFAULT_TITLE = "Demo template"


def normalize_content(content):
    return {**content, "normalized": True}


def metadata_json(content):
    return {"renderer": "demo-template"}
'''.strip(),
    "prompt_template": "Build {{ artifact_kind }} for {{ source_title }}. {{ output_instruction }}",
    "html_template": "<html><body><h1>{{ content.title }}</h1></body></html>",
    "json_schema": {
        "type": "object",
        "required": ["artifact_kind", "title"],
        "properties": {
            "artifact_kind": {"const": "demo_template"},
            "title": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "preview_content_json": {
        "artifact_kind": "demo_template",
        "title": "Demo preview",
    },
}

@pytest.fixture(autouse=True)
def isolated_artifact_plugin_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    reset_artifact_plugin_registries()
    try:
        yield tmp_path
    finally:
        reset_artifact_plugin_registries()


@pytest.fixture
async def client(isolated_artifact_plugin_home: Path):
    database_path = isolated_artifact_plugin_home / "artifact-plugins.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_artifact_plugin_api_lists_built_in_plugins(client) -> None:
    response = await client.get("/api/artifact-plugins")

    assert response.status_code == 200
    plugins = response.json()["plugins"]
    assert all(
        plugin["plugin_format"] == "template"
        for plugin in plugins
        if plugin["origin"] == "built_in"
    )
    plugin = next(plugin for plugin in plugins if plugin["artifact_kind"] == "agent_trace_graph")
    assert plugin["origin"] == "built_in"
    assert plugin["editable"] is False
    assert plugin["plugin_format"] == "template"

    source = await client.get("/api/artifact-plugins/terminal/agent_trace_graph")
    assert source.status_code == 200
    body = source.json()
    assert body["plugin_format"] == "template"
    assert "ARTIFACT_KIND" in body["python_source"]
    assert "agent-trace-graph" in body["prompt_template"]
    assert "content.nodes" in body["html_template"]
    assert body["json_schema"]["required"] == ["task", "goals", "nodes", "edges"]
    assert body["preview_content_json"]["task"] == "Diagnose delayed terminal output after remote-client reconnect"
    assert len(body["preview_content_json"]["nodes"]) >= 6
    assert set(body["preview_content_json_by_locale"]) == {"en", "zh"}
    assert body["preview_content_json_by_locale"]["en"] == body["preview_content_json"]
    assert body["preview_content_json_by_locale"]["zh"]["task"] == "诊断 remote-client 重连后终端输出延迟"
    assert len(body["preview_content_json_by_locale"]["zh"]["nodes"]) >= 6

    downloaded = await client.get("/api/artifact-plugins/terminal/agent_trace_graph/download")
    assert downloaded.status_code == 200
    download_body = downloaded.json()
    assert download_body["plugin_format"] == "template"
    assert download_body["preview_content_json"]["task"] == "Diagnose delayed terminal output after remote-client reconnect"
    assert download_body["preview_content_json_by_locale"]["zh"]["task"] == "诊断 remote-client 重连后终端输出延迟"
    assert 'filename="agent_trace_graph.json"' in downloaded.headers["content-disposition"]


@pytest.mark.asyncio
async def test_artifact_plugin_api_manages_terminal_plugin(client, tmp_path: Path) -> None:
    created = await client.post("/api/artifact-plugins/terminal", json={"source": PLUGIN_SOURCE})

    assert created.status_code == 201
    body = created.json()
    assert body["artifact_kind"] == "demo_report"
    assert body["label"] == "Demo Report"
    assert body["origin"] == "managed"
    assert body["editable"] is True
    assert body["plugin_format"] == "legacy_python"
    assert "create_plugin" in body["source"]
    assert (tmp_path / ".web-terminal-acp" / "artifact-plugins" / "terminal" / "demo_report.py").is_file()
    assert get_terminal_artifact_plugin_registry().by_kind("demo_report").label == "Demo Report"

    duplicate = await client.post("/api/artifact-plugins/terminal", json={"source": PLUGIN_SOURCE})
    assert duplicate.status_code == 409

    downloaded = await client.get("/api/artifact-plugins/terminal/demo_report/download")
    assert downloaded.status_code == 200
    assert downloaded.text == PLUGIN_SOURCE
    assert 'filename="demo_report.py"' in downloaded.headers["content-disposition"]

    updated = await client.put(
        "/api/artifact-plugins/terminal/demo_report",
        json={"source": UPDATED_PLUGIN_SOURCE},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Updated Demo Report"
    assert get_terminal_artifact_plugin_registry().by_kind("demo_report").label == "Updated Demo Report"

    deleted = await client.delete("/api/artifact-plugins/terminal/demo_report")
    assert deleted.status_code == 204

    list_after_delete = await client.get("/api/artifact-plugins")
    assert all(plugin["artifact_kind"] != "demo_report" for plugin in list_after_delete.json()["plugins"])


@pytest.mark.asyncio
async def test_artifact_plugin_api_manages_template_terminal_plugin(client, tmp_path: Path) -> None:
    created = await client.post("/api/artifact-plugins/terminal", json=TEMPLATE_PLUGIN_PAYLOAD)

    assert created.status_code == 201
    body = created.json()
    assert body["artifact_kind"] == "demo_template"
    assert body["label"] == "Demo Template"
    assert body["plugin_format"] == "template"
    assert body["python_source"] == TEMPLATE_PLUGIN_PAYLOAD["python_source"]
    assert body["prompt_template"] == TEMPLATE_PLUGIN_PAYLOAD["prompt_template"]
    assert body["html_template"] == TEMPLATE_PLUGIN_PAYLOAD["html_template"]
    assert body["json_schema"] == TEMPLATE_PLUGIN_PAYLOAD["json_schema"]
    assert body["preview_content_json"] == TEMPLATE_PLUGIN_PAYLOAD["preview_content_json"]
    plugin_dir = tmp_path / ".web-terminal-acp" / "artifact-plugins" / "terminal" / "demo_template"
    assert (plugin_dir / "plugin.py").is_file()
    assert (plugin_dir / "prompt.jinja").is_file()
    assert (plugin_dir / "display.html.jinja").is_file()
    assert (plugin_dir / "schema.json").is_file()
    assert (plugin_dir / "preview.json").is_file()

    plugin = get_terminal_artifact_plugin_registry().by_kind("demo_template")
    prompt = plugin.build_prompt(
        source_title="Demo Terminal",
        output_path="/tmp/demo-template.json",
    )
    assert "Demo Terminal" in prompt
    assert "/tmp/demo-template.json" in prompt
    content = plugin.parse_output('{"artifact_kind":"demo_template","title":"Demo"}')
    assert content["normalized"] is True
    rendered = plugin.render(content)
    assert rendered.metadata_json["renderer"] == "demo-template"
    assert "<h1>Demo</h1>" in rendered.display_html

    downloaded = await client.get("/api/artifact-plugins/terminal/demo_template/download")
    assert downloaded.status_code == 200
    assert downloaded.json()["plugin_format"] == "template"
    assert downloaded.json()["preview_content_json"] == TEMPLATE_PLUGIN_PAYLOAD["preview_content_json"]
    assert 'filename="demo_template.json"' in downloaded.headers["content-disposition"]

    preview = await client.get("/api/artifact-plugins/terminal/demo_template/preview/html")
    assert preview.status_code == 200
    assert "<h1>Demo preview</h1>" in preview.text

    draft_preview = await client.post("/api/artifact-plugins/terminal/preview/html", json={
        **TEMPLATE_PLUGIN_PAYLOAD,
        "preview_content_json": {
            "artifact_kind": "demo_template",
            "title": "Draft preview",
        },
    })
    assert draft_preview.status_code == 200
    assert "<h1>Draft preview</h1>" in draft_preview.text

    updated_payload = {
        **TEMPLATE_PLUGIN_PAYLOAD,
        "python_source": TEMPLATE_PLUGIN_PAYLOAD["python_source"].replace(
            "Demo Template",
            "Updated Demo Template",
        ),
    }
    updated = await client.put("/api/artifact-plugins/terminal/demo_template", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["label"] == "Updated Demo Template"
    assert get_terminal_artifact_plugin_registry().by_kind("demo_template").label == "Updated Demo Template"

    deleted = await client.delete("/api/artifact-plugins/terminal/demo_template")
    assert deleted.status_code == 204
    assert not plugin_dir.exists()


@pytest.mark.asyncio
async def test_artifact_plugin_api_rejects_builtin_overwrite(client) -> None:
    source = PLUGIN_SOURCE.replace("demo_report", "agent_trace_graph")

    response = await client.post("/api/artifact-plugins/terminal", json={"source": source})

    assert response.status_code == 400
    assert "built-in artifact plugin cannot be overwritten" in response.json()["detail"]


@pytest.mark.asyncio
async def test_artifact_plugin_api_update_requires_existing_managed_plugin(client) -> None:
    response = await client.put("/api/artifact-plugins/terminal/demo_report", json={"source": PLUGIN_SOURCE})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_artifact_plugin_api_surfaces_broken_managed_files(client, tmp_path: Path) -> None:
    root = tmp_path / ".web-terminal-acp" / "artifact-plugins" / "terminal"
    root.mkdir(parents=True)
    (root / "broken.py").write_text(BROKEN_PLUGIN_SOURCE)

    response = await client.get("/api/artifact-plugins")

    assert response.status_code == 200
    broken = next(plugin for plugin in response.json()["plugins"] if plugin["artifact_kind"] == "broken")
    assert broken["origin"] == "managed"
    assert broken["editable"] is True
    assert "validation_error" in broken

    with pytest.raises(ValueError, match="unsupported terminal artifact kind"):
        get_terminal_artifact_plugin_registry().by_kind("broken")


@pytest.mark.asyncio
async def test_managed_artifact_plugins_are_scoped_by_keycloak_user(
    auth_db_client,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", public_key_pem(key_pair))
    alice_token = keycloak_token(key_pair, subject="alice", username="alice")
    bob_token = keycloak_token(key_pair, subject="bob", username="bob")

    created = await auth_db_client.post(
        "/api/artifact-plugins/terminal",
        json={"source": PLUGIN_SOURCE},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob = await auth_db_client.get(
        "/api/artifact-plugins",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    alice = await auth_db_client.get(
        "/api/artifact-plugins",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert created.status_code == 201
    assert bob.status_code == 200
    assert all(plugin["artifact_kind"] != "demo_report" for plugin in bob.json()["plugins"])
    assert alice.status_code == 200
    assert any(
        plugin["artifact_kind"] == "demo_report" and plugin["origin"] == "managed"
        for plugin in alice.json()["plugins"]
    )
