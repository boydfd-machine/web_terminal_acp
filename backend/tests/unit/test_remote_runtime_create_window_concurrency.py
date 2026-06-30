from tests.unit.test_remote_runtime_support import *


class BlockingRemoteCreateConnection(FakeConnection):
    def __init__(self, client_id) -> None:
        super().__init__()
        self.client_id = client_id
        self.active = 0
        self.max_active = 0
        self.started_count = 0
        self.started = asyncio.Condition()
        self.should_continue = asyncio.Event()

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        async with self.started:
            self.active += 1
            self.started_count += 1
            self.max_active = max(self.max_active, self.active)
            self.started.notify_all()
        try:
            await self.should_continue.wait()
            return AgentMessage(
                type="create_window_result",
                client_id=self.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "remote_session_id": "client_pool",
                    "remote_window_id": f"@{self.started_count}",
                },
            )
        finally:
            async with self.started:
                self.active -= 1
                self.started.notify_all()

    async def wait_for_started_count(self, count: int) -> None:
        async with self.started:
            await asyncio.wait_for(
                self.started.wait_for(lambda: self.started_count >= count),
                timeout=1.0,
            )


@pytest.mark.asyncio
async def test_remote_runtime_create_window_requests_are_concurrency_limited() -> None:
    client_id = uuid4()
    expected_concurrency = 4
    connection = BlockingRemoteCreateConnection(client_id)
    runtime = RemoteRuntime(client_id=client_id, registry=FakeRegistry(connection), request_timeout=7.5)
    tasks = [
        asyncio.create_task(runtime.create_window(cwd="/project", window_id=uuid4()))
        for _ in range(expected_concurrency + 2)
    ]

    try:
        await connection.wait_for_started_count(expected_concurrency)
        await asyncio.sleep(0)

        assert connection.started_count == expected_concurrency
        assert connection.max_active == expected_concurrency
    finally:
        connection.should_continue.set()
        await asyncio.gather(*tasks)
