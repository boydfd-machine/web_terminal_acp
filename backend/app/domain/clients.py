from __future__ import annotations

import sys

from app.contexts.clients import domain as _domain

sys.modules[__name__] = _domain
