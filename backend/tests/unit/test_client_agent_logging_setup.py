"""Tests for the client agent logging setup with rotating file handler."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from app.client_agent.logging_setup import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_BYTES,
    LOG_FILENAME,
    STDOUT_LOG_FILENAME,
    configure_client_logging,
)


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


@pytest.fixture(autouse=True)
def _clear_log_level_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WEB_TERMINAL_CLIENT_LOG_LEVEL", raising=False)


def test_configure_client_logging_creates_logs_dir_and_file(tmp_path: Path):
    install_path = tmp_path / "wt"
    configure_client_logging(install_path)

    logs_dir = install_path / "logs"
    assert logs_dir.is_dir()
    log_path = logs_dir / LOG_FILENAME
    logging.getLogger("app.client_agent.test").info("client ready")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert log_path.is_file(), f"expected log file at {log_path}"


def test_configure_client_logging_writes_timestamped_lines(tmp_path: Path):
    configure_client_logging(tmp_path)

    logging.getLogger("app.client_agent.test").info("rolling-start")
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_path = tmp_path / "logs" / LOG_FILENAME
    text = log_path.read_text(encoding="utf-8")
    assert "rolling-start" in text
    assert "INFO" in text
    assert text.startswith("20"), f"expected ISO timestamp prefix, got: {text!r}"
    assert "Z " in text or text.split(" ", 1)[0].endswith("Z")


def test_configure_client_logging_uses_rotating_file_handler(tmp_path: Path):
    configure_client_logging(tmp_path, max_bytes=512, backup_count=3)

    file_handlers = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    ]
    assert file_handlers, "expected a RotatingFileHandler"
    handler = file_handlers[0]
    assert handler.maxBytes == 512
    assert handler.backupCount == 3


def test_configure_client_logging_rotates_when_size_exceeded(tmp_path: Path):
    configure_client_logging(tmp_path, max_bytes=256, backup_count=2)

    logger = logging.getLogger("app.client_agent.test.rotate")
    for index in range(50):
        logger.info("padding-%03d-%s", index, "x" * 40)
    for handler in logging.getLogger().handlers:
        handler.flush()
        if isinstance(handler, RotatingFileHandler):
            handler.doRollover()

    logs_dir = tmp_path / "logs"
    rotated = sorted(logs_dir.glob(f"{LOG_FILENAME}*"))
    names = [path.name for path in rotated]
    # Current client.log plus at least one rotated client.log.1
    assert LOG_FILENAME in names
    assert f"{LOG_FILENAME}.1" in names


def test_configure_client_logging_is_idempotent(tmp_path: Path):
    configure_client_logging(tmp_path)
    first = sum(
        1
        for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    )
    configure_client_logging(tmp_path)
    second = sum(
        1
        for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    )
    assert first == 1
    assert second == 1


def test_configure_client_logging_respects_env_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("WEB_TERMINAL_CLIENT_LOG_LEVEL", "DEBUG")
    configure_client_logging(tmp_path)
    assert logging.getLogger().level == logging.DEBUG


def test_configure_client_logging_honors_explicit_level(tmp_path: Path):
    configure_client_logging(tmp_path, level=logging.WARNING)
    assert logging.getLogger().level == logging.WARNING


def test_configure_client_logging_stream_handler_filters_to_warning(tmp_path: Path):
    configure_client_logging(tmp_path)
    stream_handlers = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
        and getattr(h, "_web_terminal_client_logging_configured", False) is False
        and getattr(h, "_web_terminal_stream_handler", False)
    ]
    assert stream_handlers, "expected a configured non-rotating stream handler"
    assert stream_handlers[0].level == logging.WARNING


def test_default_stdout_log_filename_matches_launcher_redirection():
    assert STDOUT_LOG_FILENAME == "client.stdout.log"


def test_defaults_match_documented_policies():
    assert DEFAULT_MAX_BYTES == 5 * 1024 * 1024
    assert DEFAULT_BACKUP_COUNT == 5
