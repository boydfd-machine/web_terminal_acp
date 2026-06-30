from __future__ import annotations

import sys

from app.contexts.activity.application import agent_activity_projection as _service

sys.modules[__name__] = _service
