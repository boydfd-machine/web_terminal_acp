from __future__ import annotations

import sys

from app.platform.plugins.agent_tools.adapters import cursor_cli as _cursor_cli

sys.modules[__name__] = _cursor_cli
