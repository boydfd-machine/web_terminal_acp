from __future__ import annotations

import sys

from app.contexts.activity.domain import event_kinds as _event_kinds

sys.modules[__name__] = _event_kinds
