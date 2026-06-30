from __future__ import annotations

import sys

from app.contexts.terminal_artifacts.api import schemas as _schemas

sys.modules[__name__] = _schemas
