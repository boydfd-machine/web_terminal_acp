"""Tests for backend logging configuration."""

from __future__ import annotations

import logging
from io import StringIO

import pytest

from app.platform.logging_config import ISO8601Formatter, configure_logging


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in saved_handlers:
            root.addHandler(handler)
        root.setLevel(saved_level)


def test_configure_logging_installs_timestamped_stream_handler():
    configure_logging()
    root = logging.getLogger()
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers, "expected at least one stream handler after configure_logging"
    formatter = stream_handlers[0].formatter
    assert isinstance(formatter, ISO8601Formatter)


def test_configure_logging_emits_iso8601_timestamps():
    configure_logging()
    root = logging.getLogger()
    stream_handler = next(h for h in root.handlers if isinstance(h, logging.StreamHandler))
    buffer = StringIO()
    original_stream = stream_handler.stream
    stream_handler.stream = buffer
    try:
        logging.getLogger("app.test_logging_config").info("hello-log")
    finally:
        stream_handler.stream = original_stream
    rendered = buffer.getvalue().strip()
    assert "INFO" in rendered
    assert "hello-log" in rendered
    assert rendered.startswith("20"), f"expected leading ISO timestamp, got: {rendered!r}"
    # ISO 8601 with millisecond precision and UTC 'Z' suffix
    assert rendered[4] == "-"
    assert rendered[10] == "T"
    assert rendered.endswith("Z") or rendered.split(" ", 1)[0].endswith("Z")


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    # Strip any handlers carried over from app.main import-time setup so we can
    # observe a clean install below.
    for handler in list(root.handlers):
        if getattr(handler, "_web_terminal_logging_configured", False):
            root.removeHandler(handler)

    configure_logging()
    first_owned = [
        h for h in root.handlers if getattr(h, "_web_terminal_logging_configured", False)
    ]
    assert len(first_owned) == 1

    configure_logging()
    configure_logging()
    second_owned = [
        h for h in root.handlers if getattr(h, "_web_terminal_logging_configured", False)
    ]
    assert len(second_owned) == 1
    assert second_owned[0] is first_owned[0]


def test_configure_logging_respects_level_string():
    configure_logging(level="DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_respects_numeric_level():
    configure_logging(level=logging.WARNING)
    assert logging.getLogger().level == logging.WARNING


def test_iso8601_formatter_renders_utc_z_suffix():
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="body",
        args=None,
        exc_info=None,
    )
    record.created = 0  # epoch
    rendered = ISO8601Formatter().formatTime(record)
    assert rendered.endswith("Z")
    assert rendered.startswith("1970-01-01T")
