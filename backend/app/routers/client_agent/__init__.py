from __future__ import annotations

import sys

from app.contexts.clients.api import client_agent as _client_agent

sys.modules[__name__] = _client_agent
