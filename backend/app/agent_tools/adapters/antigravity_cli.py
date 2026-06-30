from __future__ import annotations

import sys

from app.platform.plugins.agent_tools.adapters import antigravity_cli as _antigravity_cli

sys.modules[__name__] = _antigravity_cli
