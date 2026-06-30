from __future__ import annotations

import random

from websockets.exceptions import ConnectionClosed, InvalidMessage, InvalidStatus

_EXPECTED_RECONNECT_EXCEPTIONS = (ConnectionClosed, InvalidMessage, InvalidStatus)


def _is_expected_reconnect_exception(exc: BaseException) -> bool:
    return isinstance(exc, _EXPECTED_RECONNECT_EXCEPTIONS) or (
        isinstance(exc, OSError) and "Connect call failed" in str(exc)
    )


def _reconnect_sleep_seconds(reconnect_delay: float) -> float:
    return reconnect_delay + random.uniform(0, min(1.0, reconnect_delay * 0.25))
