from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import uuid4

Runner = Callable[[list[str]], Awaitable[str]]
InputRunner = Callable[[list[str], bytes], Awaitable[str]]
Sleeper = Callable[[float], Awaitable[None]]

DIRECT_INPUT_LITERAL_MAX_ARG_BYTES = 64 * 1024
_BRACKETED_PASTE_START = "\x1b[200~"
_COMPOSER_SUBMIT_INPUT = "\x1b[13u"


async def send_direct_input_to_tmux(
    *,
    tmux_target: str,
    data: bytes,
    run: Runner,
    run_with_stdin: InputRunner,
    sleep: Sleeper,
    submit_delay_seconds: float,
) -> None:
    text = data.decode("utf-8", errors="surrogateescape")
    literal, trailing_newline = split_direct_input_literal(text)
    if literal:
        await _send_literal(
            tmux_target=tmux_target,
            literal=literal,
            run=run,
            run_with_stdin=run_with_stdin,
            sleep=sleep,
            submit_delay_seconds=submit_delay_seconds,
        )
    if trailing_newline:
        if literal:
            await sleep(submit_delay_seconds)
        await run(["tmux", "send-keys", "-t", tmux_target, "Enter"])


def split_direct_input_literal(text: str) -> tuple[str, bool]:
    if not text:
        return "", False
    if text.startswith(_BRACKETED_PASTE_START):
        if text.endswith("\r\n"):
            return text[:-2], True
        if text.endswith("\n") or text.endswith("\r"):
            return text[:-1], True
        return text, False
    if text.endswith("\r\n"):
        return text[:-2], True
    if text.endswith("\n") or text.endswith("\r"):
        return text[:-1], True
    return text, False


async def _send_literal(
    *,
    tmux_target: str,
    literal: str,
    run: Runner,
    run_with_stdin: InputRunner,
    sleep: Sleeper,
    submit_delay_seconds: float,
) -> None:
    literal_bytes = literal.encode("utf-8", errors="surrogateescape")
    if len(literal_bytes) <= DIRECT_INPUT_LITERAL_MAX_ARG_BYTES:
        await run(["tmux", "send-keys", "-l", "-t", tmux_target, "--", literal])
        return

    buffered_literal, trailing_submit = _split_trailing_composer_submit(literal)
    if buffered_literal:
        buffer_name = _direct_input_buffer_name(tmux_target)
        await run_with_stdin(
            ["tmux", "load-buffer", "-b", buffer_name, "-"],
            buffered_literal.encode("utf-8", errors="surrogateescape"),
        )
        await run(["tmux", "paste-buffer", "-d", "-r", "-b", buffer_name, "-t", tmux_target])
    if trailing_submit:
        if buffered_literal:
            await sleep(submit_delay_seconds)
        await run(["tmux", "send-keys", "-l", "-t", tmux_target, "--", trailing_submit])


def _split_trailing_composer_submit(literal: str) -> tuple[str, str]:
    if literal.endswith(_COMPOSER_SUBMIT_INPUT):
        return literal[: -len(_COMPOSER_SUBMIT_INPUT)], _COMPOSER_SUBMIT_INPUT
    return literal, ""


def _direct_input_buffer_name(tmux_target: str) -> str:
    suffix = tmux_target.rsplit(":", 1)[-1]
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "", suffix).strip("_-") or "pane"
    return f"web-terminal-direct-input-{normalized}-{uuid4().hex}"
