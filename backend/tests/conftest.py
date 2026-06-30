from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.platform.security_store import reset_security_store_for_tests


@pytest.fixture(autouse=True)
def isolate_test_home(tmp_path_factory, monkeypatch):
    isolated_home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setattr(Path, "home", lambda: isolated_home)


@pytest.fixture(autouse=True)
async def disable_http_auth_for_legacy_tests():
    settings = get_settings()
    previous_auth = settings.web_terminal_disable_auth_for_tests
    previous_limits = settings.web_terminal_disable_security_rate_limits_for_tests
    settings.web_terminal_disable_auth_for_tests = True
    settings.web_terminal_disable_security_rate_limits_for_tests = True
    await reset_security_store_for_tests()
    try:
        yield
    finally:
        settings.web_terminal_disable_auth_for_tests = previous_auth
        settings.web_terminal_disable_security_rate_limits_for_tests = previous_limits
        await reset_security_store_for_tests()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
