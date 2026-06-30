"""Client agent logging setup.

Configures the root logger with a :class:`logging.handlers.RotatingFileHandler`
writing to ``install_path/logs/client.log`` so a long-running remote client does
not produce an unbounded log file. Every line carries an ISO 8601 UTC timestamp.

Standalone launcher scripts (``updater.py``, ``register-client-direct.sh``,
``client_update.py`` legacy path) redirect the process stdout/stderr into
``install_path/logs/client.stdout.log`` to capture import errors and unhandled
tracebacks that occur before this module can attach its handlers.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "client.log"
STDOUT_LOG_FILENAME = "client.stdout.log"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
_LEVEL_ENV_VAR = "WEB_TERMINAL_CLIENT_LOG_LEVEL"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_CONFIGURED_FLAG = "_web_terminal_client_logging_configured"


class ISO8601Formatter(logging.Formatter):
    """Formatter that renders ``record.created`` as an ISO 8601 UTC timestamp."""

    def __init__(self) -> None:
        super().__init__(fmt=_LOG_FORMAT)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure_client_logging(
    install_path: Path,
    *,
    level: int | str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    filename: str = LOG_FILENAME,
) -> logging.Logger:
    """Attach a rotating file handler for the client agent.

    Creates ``install_path/logs`` if missing, installs an idempotent
    :class:`RotatingFileHandler` on the root logger, and returns the
    ``app.client_agent`` logger for caller convenience.
    """

    logs_dir = install_path.expanduser() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / filename

    root = logging.getLogger()
    if any(getattr(handler, _CONFIGURED_FLAG, False) for handler in root.handlers):
        if level is not None:
            root.setLevel(_resolve_level(level))
        return logging.getLogger("app.client_agent")

    formatter = ISO8601Formatter()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    setattr(file_handler, _CONFIGURED_FLAG, True)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(formatter)
    setattr(stream_handler, "_web_terminal_stream_handler", True)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root.setLevel(_resolve_level(level))
    return logging.getLogger("app.client_agent")


def _resolve_level(level: int | str | None) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        normalized = level.upper()
        if normalized.isdigit():
            return int(normalized)
        return logging.getLevelName(normalized)
    env_level = os.environ.get(_LEVEL_ENV_VAR)
    if env_level:
        normalized = env_level.upper()
        if normalized.isdigit():
            return int(normalized)
        return logging.getLevelName(normalized)
    return DEFAULT_LOG_LEVEL
