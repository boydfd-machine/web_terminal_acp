from tests.integration.test_window_api_fakes import *

import io
import zipfile


def skill_zip_bytes(skill_id: str, skill_md: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{skill_id}/SKILL.md", skill_md)
    return buffer.getvalue()

def codex_message_payload(text: str, *, timestamp: datetime | None = None) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        },
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def codex_user_message_payload(text: str, *, timestamp: datetime | None = None) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

def codex_completion_payload(
    *, event_type: str = "task_completed", timestamp: datetime | None = None
) -> dict:
    payload = {
        "provider": "codex",
        "raw_type": "event_msg",
        "payload": {"type": event_type},
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp.isoformat()
    return payload

async def allow_remote_create_to_finish(connection: FakeRemoteConnection) -> None:
    await asyncio.wait_for(connection.request_started.wait(), timeout=1.0)
    connection.request_continue.set()

async def wait_for_remote_window_ready(
    db_client: "DbClient",
    client_id: str,
    window_id: str,
) -> VirtualWindow:
    for _ in range(50):
        async with db_client.session_factory() as session:
            window = await session.get(VirtualWindow, UUID(window_id))
            if (
                window is not None
                and window.client_id == UUID(client_id)
                and window.remote_session_id is not None
                and window.remote_window_id is not None
            ):
                return window
        await asyncio.sleep(0.01)
    raise AssertionError("remote window did not become ready")

async def wait_for_local_window_ready(
    db_client: "DbClient",
    client_id: str,
    window_id: str,
) -> VirtualWindow:
    for _ in range(50):
        async with db_client.session_factory() as session:
            window = await session.get(VirtualWindow, UUID(window_id))
            if (
                window is not None
                and window.client_id == UUID(client_id)
                and window.tmux_session is not None
                and window.tmux_window_id is not None
            ):
                return window
        await asyncio.sleep(0.01)
    raise AssertionError("local window did not become ready")

async def wait_for_tmux_kill_count(count: int) -> None:
    for _ in range(50):
        if len(FakeTmuxManager.killed_targets) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"tmux kill count did not reach {count}")

async def wait_for_remote_window_status(
    db_client: "DbClient",
    window_id: str,
    status: str,
) -> VirtualWindow:
    for _ in range(50):
        async with db_client.session_factory() as session:
            window = await session.get(VirtualWindow, UUID(window_id))
            if window is not None and window.status.value == status:
                return window
        await asyncio.sleep(0.01)
    raise AssertionError(f"remote window did not reach status {status}")

class DbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker):
        self._client = client
        self.session_factory = session_factory

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._client.patch(*args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._client.put(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete(*args, **kwargs)

@pytest.fixture
async def db_client(tmp_path):
    clear_polling_response_cache()
    clear_client_windows_activity_cache()
    database_path = tmp_path / "windows.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await ensure_local_client(session)
        await session.commit()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    FakeTmuxManager.killed_targets = []
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tmux_manager] = FakeTmuxManager
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield DbClient(test_client, session_factory)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_tmux_manager, None)
        for state_name in ("client_connections", "terminal_broker"):
            if hasattr(app.state, state_name):
                delattr(app.state, state_name)
        clear_polling_response_cache()
        clear_client_windows_activity_cache()
        await engine.dispose()

async def get_local_client_id(db_client: DbClient) -> str:
    response = await db_client.get("/api/clients")
    assert response.status_code == 200
    local_clients = [client for client in response.json() if client["runtime"] == "local"]
    assert len(local_clients) == 1
    return local_clients[0]["id"]

async def create_remote_client_id(db_client: DbClient, name: str = "remote-a") -> str:
    async with db_client.session_factory() as session:
        client, _token = await create_client(
            session,
            name=name,
            runtime=ClientRuntime.remote,
        )
        client_id = str(client.id)
        await session.commit()
    return client_id

def worktree_marker(
    window_id: UUID,
    *,
    worktree_root: str = "/repo/.worktrees/feature",
    main_repo_root: str = "/repo",
    branch: str = "agent/feature",
) -> str:
    payload = {
        "worktree_root": worktree_root,
        "main_repo_root": main_repo_root,
        "branch": branch,
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return f"\x1b]777;web-terminal-worktree;window_id={window_id};payload={encoded}\x07"

def tracking_sequence(worktree_root: str) -> str:
    digest = sha256(worktree_root.encode("utf-8")).hexdigest()[:16]
    return f"worktree:{digest}"

def parse_response_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _tree_contains_path(nodes, path):
    for node in nodes:
        if node["path"] == path:
            return True
        if _tree_contains_path(node["folders"], path):
            return True
    return False

__all__ = [name for name in globals() if not name.startswith("__")]
