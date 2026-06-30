from __future__ import annotations

import sys

from app.contexts.windows.application import runtime_capabilities as _runtime_capabilities

sys.modules[__name__] = _runtime_capabilities
