from __future__ import annotations

import sys

from app.contexts.windows.application import launch_plans as _launch_plans

sys.modules[__name__] = _launch_plans
