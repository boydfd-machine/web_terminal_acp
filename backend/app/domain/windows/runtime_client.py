from __future__ import annotations

import sys

from app.contexts.windows.domain import runtime_client as _runtime_client

sys.modules[__name__] = _runtime_client
