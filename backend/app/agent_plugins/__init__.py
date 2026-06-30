from __future__ import annotations

import sys

from app.platform.plugins import agent_plugins as _agent_plugins
from app.platform.plugins.agent_plugins import builtins as _builtins
from app.platform.plugins.agent_plugins import registry as _registry
from app.platform.plugins.agent_plugins import types as _types

sys.modules[__name__] = _agent_plugins
sys.modules[f"{__name__}.builtins"] = _builtins
sys.modules[f"{__name__}.registry"] = _registry
sys.modules[f"{__name__}.types"] = _types
