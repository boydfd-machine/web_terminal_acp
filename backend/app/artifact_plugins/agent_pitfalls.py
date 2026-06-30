from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import agent_pitfalls as _agent_pitfalls

sys.modules[__name__] = _agent_pitfalls
