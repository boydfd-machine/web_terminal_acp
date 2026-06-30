from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import broker as _broker

sys.modules[__name__] = _broker
