from __future__ import annotations

import sys

from app.platform.plugins import agent_tools as _agent_tools
from app.platform.plugins.agent_tools import common as _common
from app.platform.plugins.agent_tools import registry as _registry
from app.platform.plugins.agent_tools import types as _types
from app.platform.plugins.agent_tools import user_input as _user_input
from app.platform.plugins.agent_tools import adapters as _adapters
from app.platform.plugins.agent_tools.adapters import antigravity_cli as _antigravity_cli
from app.platform.plugins.agent_tools.adapters import antigravity_subagents as _antigravity_subagents
from app.platform.plugins.agent_tools.adapters import claude_code as _claude_code
from app.platform.plugins.agent_tools.adapters import claude_code_subagents as _claude_code_subagents
from app.platform.plugins.agent_tools.adapters import codex as _codex
from app.platform.plugins.agent_tools.adapters import cursor_cli as _cursor_cli

sys.modules[__name__] = _agent_tools
sys.modules[f"{__name__}.adapters"] = _adapters
sys.modules[f"{__name__}.adapters.antigravity_cli"] = _antigravity_cli
sys.modules[f"{__name__}.adapters.antigravity_subagents"] = _antigravity_subagents
sys.modules[f"{__name__}.adapters.claude_code"] = _claude_code
sys.modules[f"{__name__}.adapters.claude_code_subagents"] = _claude_code_subagents
sys.modules[f"{__name__}.adapters.codex"] = _codex
sys.modules[f"{__name__}.adapters.cursor_cli"] = _cursor_cli
sys.modules[f"{__name__}.common"] = _common
sys.modules[f"{__name__}.registry"] = _registry
sys.modules[f"{__name__}.types"] = _types
sys.modules[f"{__name__}.user_input"] = _user_input
