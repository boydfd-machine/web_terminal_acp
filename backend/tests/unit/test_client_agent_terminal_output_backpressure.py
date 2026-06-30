from tests.unit.test_client_agent_terminal_support import *

@pytest.mark.asyncio
async def test_pipe_output_keeps_draining_pty_when_sender_back_pressures(monkeypatch) -> None:
    """The PTY reader must keep emptying the master fd even while the sender is
    stalled, so that a busy tmux pane never blocks user input through the same
    PTY. Regression for the case where typing into one terminal froze whenever
    another terminal was streaming heavy codex output.
    """

    pending_chunks = [b"chunk-1", b"chunk-2", b"chunk-3", b"chunk-4"]
    chunks_read_event = asyncio.Event()
    release_sender = asyncio.Event()
    sender_started_event = asyncio.Event()
    sender_calls: list[bytes] = []

    def fake_read(fd: int, size: int) -> bytes:
        if pending_chunks:
            return pending_chunks.pop(0)
        chunks_read_event.set()
        raise OSError

    async def slow_sender(data: bytes) -> None:
        sender_calls.append(data)
        sender_started_event.set()
        await release_sender.wait()

    async def fake_run(args: list[str]) -> str:
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@7\n"
        if args == ["tmux", "has-session", "-t", "web_terminal_view__7"]:
            return ""
        return ""

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(client_terminal.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(client_terminal, "_configure_pty_slave", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "close", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "read", fake_read)
    monkeypatch.setattr(client_terminal.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    await multiplexer.attach(WINDOW_ID, slow_sender)

    # First chunk reaches the sender, which then blocks.
    await asyncio.wait_for(sender_started_event.wait(), timeout=1)
    assert sender_calls == [b"chunk-1"]

    # While the sender is stalled the PTY reader must keep draining; it should
    # consume every remaining read (including the OSError that terminates it).
    await asyncio.wait_for(chunks_read_event.wait(), timeout=1)
    assert pending_chunks == []

    # Release the sender. The remaining bytes were coalesced inside the in-memory
    # buffer while the sender was stuck and must be delivered in order.
    release_sender.set()

    deadline = asyncio.get_event_loop().time() + 1
    while b"".join(sender_calls) != b"chunk-1chunk-2chunk-3chunk-4":
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"sender did not receive coalesced remainder: {sender_calls!r}"
            )
        await asyncio.sleep(0.01)

    await multiplexer.detach(WINDOW_ID)
    assert b"".join(sender_calls) == b"chunk-1chunk-2chunk-3chunk-4"

@pytest.mark.asyncio
async def test_pipe_output_sends_large_drained_buffer_in_small_chunks(monkeypatch) -> None:
    oversized_output = b"A" * (PTY_OUTPUT_SEND_CHUNK_BYTES * 2 + 17)
    sender_calls: list[bytes] = []
    first_chunk_sent = asyncio.Event()

    def fake_read(fd: int, size: int) -> bytes:
        if fake_read.pending:
            fake_read.pending = False
            return oversized_output
        raise OSError

    fake_read.pending = True

    async def sender(data: bytes) -> None:
        sender_calls.append(data)
        first_chunk_sent.set()

    async def fake_run(args: list[str]) -> str:
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@7\n"
        if args == ["tmux", "has-session", "-t", "web_terminal_view__7"]:
            return ""
        return ""

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(client_terminal.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(client_terminal, "_configure_pty_slave", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "close", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "read", fake_read)
    monkeypatch.setattr(client_terminal.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    await multiplexer.attach(WINDOW_ID, sender)
    await asyncio.wait_for(first_chunk_sent.wait(), timeout=1)

    deadline = asyncio.get_event_loop().time() + 1
    while b"".join(sender_calls) != oversized_output:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"sender did not receive all chunks: {list(map(len, sender_calls))}")
        await asyncio.sleep(0.01)

    await multiplexer.detach(WINDOW_ID)
    assert [len(chunk) for chunk in sender_calls] == [
        PTY_OUTPUT_SEND_CHUNK_BYTES,
        PTY_OUTPUT_SEND_CHUNK_BYTES,
        17,
    ]

@pytest.mark.asyncio
async def test_pipe_output_drops_oldest_bytes_when_buffer_overflows(monkeypatch) -> None:
    """When the downstream is so slow that the in-memory buffer would grow past
    the configured cap, the reader must drop the oldest bytes instead of
    blocking the PTY. This keeps tmux responsive even under pathological
    back-pressure.
    """

    chunk_size = 64 * 1024
    # Produce twice the buffer cap so dropping must happen somewhere.
    num_chunks = (PTY_DRAIN_BUFFER_MAX_BYTES * 2) // chunk_size
    pending_chunks = [b"A" * chunk_size for _ in range(num_chunks)]
    # Sentinel is the very last chunk; it must survive at the tail.
    sentinel = b"Z" * 1024
    pending_chunks.append(sentinel)
    release_sender = asyncio.Event()
    sender_started_event = asyncio.Event()
    sender_calls: list[bytes] = []

    def fake_read(fd: int, size: int) -> bytes:
        if pending_chunks:
            return pending_chunks.pop(0)
        raise OSError

    async def stalled_sender(data: bytes) -> None:
        sender_calls.append(data)
        sender_started_event.set()
        await release_sender.wait()

    async def fake_run(args: list[str]) -> str:
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@7\n"
        return ""

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(client_terminal.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(client_terminal, "_configure_pty_slave", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "close", lambda fd: None)
    monkeypatch.setattr(client_terminal.os, "read", fake_read)
    monkeypatch.setattr(client_terminal.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    await multiplexer.attach(WINDOW_ID, stalled_sender)

    await asyncio.wait_for(sender_started_event.wait(), timeout=2)
    # While the sender is stuck on the first chunk, the reader keeps draining
    # the (mocked) PTY into the in-memory buffer. Poll the shared list (no
    # asyncio.Event.set across threads) until the reader has emptied every
    # pending chunk, proving it never stalled.
    loop = asyncio.get_event_loop()
    deadline = loop.time() + 5
    while pending_chunks:
        if loop.time() > deadline:
            raise AssertionError(
                f"reader did not finish draining pending chunks (left={len(pending_chunks)})"
            )
        await asyncio.sleep(0.02)

    # Release the sender so the drainer can deliver the coalesced remainder.
    release_sender.set()

    # The coalesced remainder must end with the sentinel; the reader keeps the
    # most recent bytes when it drops on overflow.
    deadline = loop.time() + 5
    while True:
        combined = b"".join(sender_calls)
        if combined.endswith(sentinel):
            break
        if loop.time() > deadline:
            raise AssertionError(
                f"sender did not receive sentinel; got {len(combined)} bytes, "
                f"tail={combined[-200:]!r}"
            )
        await asyncio.sleep(0.02)

    await multiplexer.detach(WINDOW_ID)

    combined = b"".join(sender_calls)
    total_produced = num_chunks * chunk_size + len(sentinel)
    # Drops must have happened: total delivered is strictly less than total
    # produced (otherwise no back-pressure mitigation occurred).
    assert len(combined) < total_produced
    assert combined.endswith(sentinel)
