from __future__ import annotations

import sys

from app.contexts.clients.api import schemas as _schemas

sys.modules[__name__] = _schemas
