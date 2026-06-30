from __future__ import annotations

import sys

from app.platform.plugins.agent_tools.adapters import codex as _codex

sys.modules[__name__] = _codex
