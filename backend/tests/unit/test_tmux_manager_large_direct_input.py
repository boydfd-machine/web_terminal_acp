from tests.unit.test_tmux_manager_support import *


@pytest.mark.asyncio
async def test_send_input_direct_uses_tmux_buffer_for_large_composer_submitted_paste(monkeypatch) -> None:
    manager, calls, loaded_buffers, sleep_calls = _manager_with_captured_direct_input(monkeypatch)
    payload = b"\x1b[200~Todo: large dispatch\n" + b"x" * 150_000 + b"\n\x1b[201~\x1b[13u"

    await manager.send_input_direct(TmuxTarget(session="web_terminal_acp_pool", window_id="@42"), payload)

    buffer_name = _assert_tmux_buffer_paste(calls, "web-terminal-direct-input-42-", "web_terminal_acp_pool:@42")
    assert calls[1][5] == buffer_name
    assert calls[2] == ["tmux", "send-keys", "-l", "-t", "web_terminal_acp_pool:@42", "--", "\x1b[13u"]
    assert all("x" * 10_000 not in part for call in calls for part in call)
    assert loaded_buffers == [payload.removesuffix(b"\x1b[13u")]
    assert sleep_calls == [tmux_manager.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]


@pytest.mark.asyncio
async def test_send_input_direct_uses_tmux_buffer_for_large_enter_submitted_paste(monkeypatch) -> None:
    manager, calls, loaded_buffers, sleep_calls = _manager_with_captured_direct_input(monkeypatch)
    payload = b"\x1b[200~Todo: large claude dispatch\n" + b"x" * 150_000 + b"\n\x1b[201~\n"

    await manager.send_input_direct(TmuxTarget(session="web_terminal_acp_pool", window_id="@42"), payload)

    _assert_tmux_buffer_paste(calls, "web-terminal-direct-input-42-", "web_terminal_acp_pool:@42")
    assert calls[2] == ["tmux", "send-keys", "-t", "web_terminal_acp_pool:@42", "Enter"]
    assert loaded_buffers == [payload.removesuffix(b"\n")]
    assert sleep_calls == [tmux_manager.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]


def _manager_with_captured_direct_input(monkeypatch):
    calls: list[list[str]] = []
    loaded_buffers: list[bytes] = []
    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    async def fake_run_with_stdin(args: list[str], stdin: bytes) -> str:
        calls.append(args)
        loaded_buffers.append(stdin)
        return ""

    monkeypatch.setattr(tmux_manager.asyncio, "sleep", fake_sleep)
    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)
    monkeypatch.setattr(manager, "_run_with_stdin", fake_run_with_stdin)
    return manager, calls, loaded_buffers, sleep_calls


def _assert_tmux_buffer_paste(calls: list[list[str]], buffer_prefix: str, tmux_target: str) -> str:
    assert calls[0][:3] == ["tmux", "load-buffer", "-b"]
    buffer_name = calls[0][3]
    assert buffer_name.startswith(buffer_prefix)
    assert calls[0][-1] == "-"
    assert calls[1] == ["tmux", "paste-buffer", "-d", "-r", "-b", buffer_name, "-t", tmux_target]
    return buffer_name
