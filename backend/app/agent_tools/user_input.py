from __future__ import annotations

import sys

from app.platform.plugins.agent_tools import user_input as _user_input

sys.modules[__name__] = _user_input
