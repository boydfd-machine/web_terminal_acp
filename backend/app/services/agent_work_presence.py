from __future__ import annotations

import sys

from app.contexts.activity.application import agent_work_presence as _service

sys.modules[__name__] = _service
