from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status

from app.contexts.activity.domain.terminal_time_range import (
    TERMINAL_TIME_RANGE_DAYS,
    TerminalTimeRange,
    TerminalTimeRangeError,
)


def terminal_visible_since(range_value: str | None, *, now: datetime | None = None) -> datetime | None:
    try:
        return TerminalTimeRange(range_value).visible_since(now=now)
    except TerminalTimeRangeError as exc:
        allowed = ", ".join([*TERMINAL_TIME_RANGE_DAYS.keys(), "all"])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid terminal time range; expected one of: {allowed}",
        ) from exc
