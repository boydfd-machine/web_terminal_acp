from __future__ import annotations

import sys

from app.platform.plugins.agent_tools import registry as _registry

sys.modules[__name__] = _registry
