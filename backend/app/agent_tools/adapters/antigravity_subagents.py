from __future__ import annotations

import sys

from app.platform.plugins.agent_tools.adapters import antigravity_subagents as _antigravity_subagents

sys.modules[__name__] = _antigravity_subagents
