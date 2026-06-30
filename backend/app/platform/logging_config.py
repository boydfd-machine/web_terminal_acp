"""Backend logging configuration with ISO 8601 timestamps.

Provides :func:`configure_logging`, which installs a :class:`logging.StreamHandler`
on the root logger with a timestamped formatter. The handler is idempotent so
calling it from both FastAPI startup and standalone CLI entry points does not
duplicate log lines.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DEFAULT_LEVEL = logging.INFO
_CONFIGURED_FLAG = "_web_terminal_logging_configured"


class ISO8601Formatter(logging.Formatter):
    """Formatter that renders ``record.created`` as an ISO 8601 UTC timestamp."""

    def __init__(self, fmt: str | None = None) -> None:
        super().__init__(fmt=fmt or _LOG_FORMAT)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure_logging(level: int | str | None = None) -> None:
    """Install a timestamped stream handler on the root logger.

    Repeated calls are a no-op once a configured handler is present so callers
    such as FastAPI startup and standalone worker scripts can both invoke it.
    """

    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, _CONFIGURED_FLAG, False):
            if level is not None:
                root.setLevel(_resolve_level(level))
            return

    handler = logging.StreamHandler()
    handler.setFormatter(ISO8601Formatter())
    setattr(handler, _CONFIGURED_FLAG, True)
    root.addHandler(handler)
    root.setLevel(_resolve_level(level))


def _resolve_level(level: int | str | None) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        normalized = level.upper()
        if normalized.isdigit():
            return int(normalized)
        return logging.getLevelName(normalized)
    return _DEFAULT_LEVEL
