from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

TERMINAL_TIME_RANGE_DAYS = {
    "1d": 1,
    "3d": 3,
    "5d": 5,
    "7d": 7,
    "14d": 14,
    "30d": 30,
}


class TerminalTimeRangeError(ValueError):
    pass


@dataclass(frozen=True)
class TerminalTimeRange:
    raw_value: str | None

    @property
    def cache_token(self) -> str:
        return self.raw_value or "all"

    def visible_since(self, *, now: datetime | None = None) -> datetime | None:
        if self.raw_value in (None, "", "all"):
            return None

        days = TERMINAL_TIME_RANGE_DAYS.get(self.raw_value)
        if days is None:
            allowed = ", ".join([*TERMINAL_TIME_RANGE_DAYS.keys(), "all"])
            raise TerminalTimeRangeError(
                f"invalid terminal time range; expected one of: {allowed}"
            )

        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        return current - timedelta(days=days)
