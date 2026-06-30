from __future__ import annotations

import sys

from app.contexts.activity.application import terminal_work_status as _terminal_work_status

sys.modules[__name__] = _terminal_work_status
sys.modules[f"{__name__}.status_service"] = _terminal_work_status
sys.modules[f"{__name__}.agent_activity_queries"] = _terminal_work_status
sys.modules[f"{__name__}.terminal_activity_queries"] = _terminal_work_status
