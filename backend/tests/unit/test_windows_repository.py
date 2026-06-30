from datetime import UTC, datetime

import pytest

from app.contexts.windows.infrastructure.repository import fallback_terminal_title


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 6, 6, 5, 56, tzinfo=UTC), "Terminal 06/06 13:56"),
        (datetime(2026, 6, 5, 21, 56, tzinfo=UTC), "Terminal 06/06 05:56"),
    ],
)
def test_fallback_terminal_title_uses_utc_plus_8_month_day_hour_minute(now, expected):
    assert fallback_terminal_title(now) == expected
