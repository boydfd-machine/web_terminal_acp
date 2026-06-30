from __future__ import annotations

import sys

from app.platform.plugins.agent_tools.adapters import claude_code as _claude_code

sys.modules[__name__] = _claude_code
