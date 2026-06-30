from __future__ import annotations

import sys

from app.platform.plugins.agent_tools import adapters as _adapters
from app.platform.plugins.agent_tools.adapters import antigravity_cli as _antigravity_cli
from app.platform.plugins.agent_tools.adapters import antigravity_subagents as _antigravity_subagents
from app.platform.plugins.agent_tools.adapters import claude_code as _claude_code
from app.platform.plugins.agent_tools.adapters import claude_code_subagents as _claude_code_subagents
from app.platform.plugins.agent_tools.adapters import codex as _codex
from app.platform.plugins.agent_tools.adapters import cursor_cli as _cursor_cli

sys.modules[__name__] = _adapters
sys.modules[f"{__name__}.antigravity_cli"] = _antigravity_cli
sys.modules[f"{__name__}.antigravity_subagents"] = _antigravity_subagents
sys.modules[f"{__name__}.claude_code"] = _claude_code
sys.modules[f"{__name__}.claude_code_subagents"] = _claude_code_subagents
sys.modules[f"{__name__}.codex"] = _codex
sys.modules[f"{__name__}.cursor_cli"] = _cursor_cli
