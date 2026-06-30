from tests.unit.test_client_agent_runner_support import *


class CountingBlockingCreateRuntime(FakeRuntime):
    def __init__(self) -> None:
        super().__init__([])
        self.active = 0
        self.max_active = 0
        self.started_count = 0
        self.started = asyncio.Condition()
        self.should_continue = asyncio.Event()

    async def create_window(self, window_id, *, cwd=None, shell_command=None, agent_ops_token=None):
        async with self.started:
            self.active += 1
            self.started_count += 1
            self.max_active = max(self.max_active, self.active)
            self.started.notify_all()
        try:
            await self.should_continue.wait()
            return ClientRuntimeWindow(
                remote_session_id="pool",
                remote_window_id=f"@{self.started_count}",
                local_window_id=window_id,
                cwd=cwd,
                shell_command=shell_command,
                managed_agent_tools=True,
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
async def test_create_window_background_jobs_are_concurrency_limited() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    expected_concurrency = 4
    runtime = CountingBlockingCreateRuntime()
    create_window_tasks: set[asyncio.Task[None]] = set()

    try:
        for index in range(expected_concurrency + 2):
            await _handle_agent_message(
                FakeWriter(),
                FakeBulkWriter(),
                object(),
                runtime,
                FakeTerminal([]),
                FakeIdleSupervisor([]),
                FakeAgentToolWatcher([]),
                FakeAuxTerminal(),
                {},
                set(),
                asyncio.Semaphore(1),
                {},
                AgentMessage(
                    type="create_window",
                    client_id=client_id,
                    window_id=UUID(f"87654321-4321-8765-4321-{index + 1:012d}"),
                    request_id=f"create-{index}",
                    payload={"cwd": "/workspace/project"},
                ),
                create_window_tasks=create_window_tasks,
            )

        await runtime.wait_for_started_count(expected_concurrency)
        await asyncio.sleep(0)

        assert runtime.started_count == expected_concurrency
        assert runtime.max_active == expected_concurrency
    finally:
        runtime.should_continue.set()
        if create_window_tasks:
            await asyncio.gather(*create_window_tasks)
