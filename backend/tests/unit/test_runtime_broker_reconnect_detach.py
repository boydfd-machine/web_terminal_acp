from tests.unit.test_runtime_broker_support import *

@pytest.mark.asyncio
async def test_reconnect_waits_for_pending_final_detach_before_reattaching() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    browser_window_id = uuid4()
    runtime_window = RuntimeWindow(session_id="session", window_id="@5")
    runtime = FakeRuntime()
    runtime.allow_detach = asyncio.Event()
    broker = TerminalBroker()
    broker.register_runtime(client_id, runtime)

    async def first_sender(data: bytes) -> None:
        return None

    async def reconnect_sender(data: bytes) -> None:
        return None

    await broker.subscribe(client_id, browser_window_id, first_sender)
    await broker.attach(client_id, browser_window_id, runtime_window)

    unsubscribe_task = asyncio.create_task(
        broker.unsubscribe(client_id, browser_window_id, first_sender)
    )
    await runtime.detach_started.wait()

    subscribe_completed = asyncio.Event()
    attach_completed = asyncio.Event()

    async def reconnect() -> None:
        await broker.subscribe(client_id, browser_window_id, reconnect_sender)
        subscribe_completed.set()
        await broker.attach(client_id, browser_window_id, runtime_window)
        attach_completed.set()

    reconnect_task = asyncio.create_task(reconnect())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    subscribe_completed_while_detaching = subscribe_completed.is_set()
    attach_completed_while_detaching = attach_completed.is_set()

    runtime.allow_detach.set()
    await unsubscribe_task
    await reconnect_task

    assert subscribe_completed_while_detaching
    assert not attach_completed_while_detaching
    assert runtime.detached == [runtime_window]
    assert runtime.attached == [runtime_window, runtime_window]
    await broker.unsubscribe(client_id, browser_window_id, reconnect_sender)
