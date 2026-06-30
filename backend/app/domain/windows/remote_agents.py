from __future__ import annotations

import sys

from app.contexts.windows.domain import remote_agents as _remote_agents

sys.modules[__name__] = _remote_agents
