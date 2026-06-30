from __future__ import annotations

import sys

from app.platform.plugins.agent_plugins import builtins as _builtins

sys.modules[__name__] = _builtins
