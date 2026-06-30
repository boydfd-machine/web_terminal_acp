from tests.unit.test_client_agent_terminal_support import *


@pytest.mark.asyncio
async def test_send_input_direct_uses_tmux_buffer_for_large_bracketed_paste(monkeypatch) -> None:
    multiplexer, calls, loaded_buffers, sleep_calls = _multiplexer_with_captured_direct_input(monkeypatch)
    payload = b"\x1b[200~Todo: large dispatch\n" + b"x" * 150_000 + b"\n\x1b[201~\x1b[13u"

    await multiplexer.send_input_direct(WINDOW_ID, payload)

    buffer_name = _assert_tmux_buffer_paste(calls)
    assert calls[1][5] == buffer_name
    assert calls[2] == ["tmux", "send-keys", "-l", "-t", "client_pool:@7", "--", "\x1b[13u"]
    assert all("x" * 10_000 not in part for call in calls for part in call)
    assert loaded_buffers == [payload.removesuffix(b"\x1b[13u")]
    assert sleep_calls == [client_terminal.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]


@pytest.mark.asyncio
async def test_send_input_direct_uses_tmux_buffer_for_large_enter_submitted_paste(monkeypatch) -> None:
    multiplexer, calls, loaded_buffers, sleep_calls = _multiplexer_with_captured_direct_input(monkeypatch)
    payload = b"\x1b[200~Todo: large claude dispatch\n" + b"x" * 150_000 + b"\n\x1b[201~\n"

    await multiplexer.send_input_direct(WINDOW_ID, payload)

    _assert_tmux_buffer_paste(calls)
    assert calls[2] == ["tmux", "send-keys", "-t", "client_pool:@7", "Enter"]
    assert loaded_buffers == [payload.removesuffix(b"\n")]
    assert sleep_calls == [client_terminal.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]


def _multiplexer_with_captured_direct_input(monkeypatch):
    calls: list[list[str]] = []
    sleep_calls: list[float] = []
    loaded_buffers: list[bytes] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(client_terminal.asyncio, "sleep", fake_sleep)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    async def fake_run_with_stdin(args: list[str], stdin: bytes) -> str:
        calls.append(args)
        loaded_buffers.append(stdin)
        return ""

    monkeypatch.setattr(multiplexer, "_run_with_stdin", fake_run_with_stdin)
    return multiplexer, calls, loaded_buffers, sleep_calls


def _assert_tmux_buffer_paste(calls: list[list[str]]) -> str:
    assert calls[0][:3] == ["tmux", "load-buffer", "-b"]
    buffer_name = calls[0][3]
    assert buffer_name.startswith("web-terminal-direct-input-7-")
    assert calls[0][-1] == "-"
    assert calls[1] == [
        "tmux",
        "paste-buffer",
        "-d",
        "-r",
        "-b",
        buffer_name,
        "-t",
        "client_pool:@7",
    ]
    return buffer_name
