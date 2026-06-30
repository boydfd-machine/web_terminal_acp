from __future__ import annotations

import sys

from app.contexts.workspace.application import summary_scheduler as _summary_scheduler

sys.modules[__name__] = _summary_scheduler
