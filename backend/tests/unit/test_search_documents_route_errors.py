from tests.unit.test_search_documents_support import *

@pytest.mark.asyncio
async def test_search_route_rejects_overlong_query(client):
    response = await client.get("/api/search", params={"q": "x" * 513})

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_search_route_returns_503_when_search_fails(client, monkeypatch):
    es_client = FakeRouteClient()

    async def failing_search_all(client_arg, query, client_id, *, include_legacy_local_documents=False):
        assert include_legacy_local_documents is True
        raise TransportError("Elasticsearch unavailable")

    app.dependency_overrides[search_router.get_search_client] = lambda: es_client
    monkeypatch.setattr(search_router, "search_all", failing_search_all)

    try:
        response = await client.get("/api/search", params={"q": "nginx"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "search service unavailable"}
    assert es_client.closed is False
